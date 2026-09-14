#!/usr/bin/env python3
"""
Stream-submit every IFC file in a large .tar.gz to the buildingSMART
Validation Service REST API, one file at a time.

Why this shape
--------------
* The archive is ~114 GB. It is never expanded: the tar is opened in gzip
  *streaming* mode ('r|gz') and walked in a single sequential pass. Each member
  is written to ONE reusable scratch file, uploaded, then deleted, so peak extra
  disk usage is one file (bounded by --max-mb), not the whole archive.
* Members ending in `.ifc`    -> uploaded as-is.
  Members ending in `.ifc.gz` -> gunzipped on the fly and uploaded under the
  `.ifc` name, because the API rejects any `file_name` not ending in `.ifc`.
  Anything else                -> skipped and recorded.
* Submissions are sequential. The endpoint is per-user throttled, so a 429 is a
  normal event, not an error: Retry-After is honoured and the same file retried.
* Every validation subtask is wrapped in a per-USER redis lock
  (`core/redis_lock.py`, key `lock:celery:user:<id>:task:<task_name>`), so a
  single user processes one task of each type at a time. Submitting everything
  as one user therefore caps throughput at roughly the slowest single task
  (~25-30 files/hour observed). Pass several tokens to --token to rotate users
  round-robin and get real parallelism -- but note each request is then owned by
  a different user, and the API/UI only shows a user their own requests.
* Every finished member is appended to --state (JSONL), so re-running skips work
  already done (the stream is still walked, but nothing is written or uploaded).

Only the standard library is used, so this runs on a stock Ubuntu host.

Examples
--------
    # smoke test: first 5 IFC members only, verbose
    ./bulk_submit.py --limit 5 --verbose

    # full run, detached, resumable
    nohup ./bulk_submit.py --state run1.jsonl --log run1.jsonl \\
        >> run1.out 2>&1 &

    # parallel across 4 users (4 independent lock domains)
    ./bulk_submit.py --token "$T1,$T2,$T3,$T4" --state run1.jsonl

    # dry run: show what would be submitted
    ./bulk_submit.py --dry-run --limit 50
"""

from __future__ import annotations

import argparse
import gzip
import http.client
import json
import os
import random
import shlex
import signal
import sys
import tarfile
import time
import urllib.parse
from datetime import datetime, timezone

CHUNK = 256 * 1024


# --------------------------------------------------------------------------- #
# multipart streaming
# --------------------------------------------------------------------------- #
class MultipartStream:
    """
    A minimal read()able object that yields a complete multipart/form-data body
    without ever holding the file in memory. http.client pulls from this with
    read(blocksize); we must supply an exact Content-Length ourselves.
    """

    def __init__(self, segments):
        # segments: list of `bytes` or `('f', path)` tuples
        self._segments = list(segments)
        self._i = 0
        self._fh = None

    def __len__(self) -> int:
        total = 0
        for seg in self._segments:
            total += len(seg) if isinstance(seg, (bytes, bytearray)) else os.path.getsize(seg[1])
        return total

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = sys.maxsize
        out = bytearray()
        while len(out) < n:
            if self._i >= len(self._segments):
                break
            item = self._segments[self._i]
            want = n - len(out)

            if isinstance(item, (bytes, bytearray)):
                out += item[:want]
                rest = item[len(item[:want]):]
                if rest:
                    self._segments[self._i] = rest
                else:
                    self._i += 1
            else:
                if self._fh is None:
                    self._fh = open(item[1], "rb")
                data = self._fh.read(want)
                if data:
                    out += data
                else:
                    self._fh.close()
                    self._fh = None
                    self._i += 1
        return bytes(out)

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def log(msg: str, verbose_only: bool = False, verbose: bool = True):
    if verbose_only and not verbose:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sanitize_part_filename(name: str) -> str:
    """
    The multipart `filename=` token becomes the on-disk name Django stores.
    Keep it recognisable but strip anything that would break the header.
    """
    base = os.path.basename(name)
    out = []
    for ch in base:
        if ch in '"\\\r\n' or ord(ch) < 32:
            out.append("_")
        else:
            out.append(ch)
    cleaned = "".join(out).strip() or "unnamed.ifc"
    # keep the .ifc suffix intact
    if not cleaned.lower().endswith(".ifc"):
        cleaned += ".ifc"
    return cleaned


def classify(name: str):
    """
    Returns (kind, upload_name) where kind is 'plain' | 'gzip' | None.
    """
    base = os.path.basename(name)
    lower = base.lower()
    if lower.endswith(".gz"):
        inner = base[:-3]
        if inner.lower().endswith(".ifc"):
            return "gzip", inner
        return None, None
    if lower.endswith(".ifc"):
        return "plain", base
    return None, None


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Api:
    def __init__(self, url: str, token: str, timeout: float):
        parts = urllib.parse.urlsplit(url)
        self.secure = parts.scheme == "https"
        self.host = parts.hostname
        self.port = parts.port or (443 if self.secure else 80)
        self.path = parts.path or "/"
        if parts.query:
            self.path += "?" + parts.query
        self.token = token
        self.timeout = timeout

    def _conn(self):
        cls = http.client.HTTPSConnection if self.secure else http.client.HTTPConnection
        return cls(self.host, self.port, timeout=self.timeout)

    def post_file(self, path: str, upload_name: str) -> tuple[int, dict, str, float | None]:
        """
        Returns (status, headers, body_text, retry_after_seconds)
        """
        boundary = "----bsivalidate" + random.getrandbits(128).to_bytes(16, "big").hex()
        part_name = sanitize_part_filename(upload_name)
        preamble = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file_name"\r\n\r\n'
            f"{upload_name}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{part_name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        epilogue = f"\r\n--{boundary}--\r\n".encode("utf-8")

        body = MultipartStream([preamble, ("f", path), epilogue])
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "application/json",
            "User-Agent": "bsi-bulk-submit/1.0",
        }

        conn = self._conn()
        try:
            conn.request("POST", self.path, body=body, headers=headers)
            resp = conn.getresponse()
            text = resp.read().decode("utf-8", "replace")
            retry_after = None
            if resp.status == 429:
                ra = resp.getheader("Retry-After")
                if ra:
                    try:
                        retry_after = float(ra)
                    except ValueError:
                        retry_after = None
            return resp.status, dict(resp.getheaders()), text, retry_after
        finally:
            body.close()
            conn.close()


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    ap.add_argument("--tar", default=os.path.expanduser("~/files.tar.gz"))
    ap.add_argument("--url", default="http://localhost/api/v1/validationrequest/",
                    help="must be reachable under ALLOWED_HOSTS (default: localhost)")
    ap.add_argument("--token", default=os.environ.get("BSI_API_TOKEN", ""),
                    help="DRF token, or several comma-separated tokens to rotate "
                         "users round-robin (or set BSI_API_TOKEN)")
    ap.add_argument("--tmpdir", default=os.path.expanduser("~/bulk_tmp"),
                    help="scratch dir for the one-at-a-time extraction")
    ap.add_argument("--state", default=None, help="JSONL file recording completed members")
    ap.add_argument("--log", default=None, help="JSONL file recording every attempt")
    ap.add_argument("--max-mb", type=int, default=256, help="API per-file limit (default 256)")
    ap.add_argument("--timeout", type=float, default=900.0, help="HTTP timeout seconds")
    ap.add_argument("--limit", type=int, default=0, help="stop after N successful submits")
    ap.add_argument("--start-index", type=int, default=0, help="skip members before this index")
    ap.add_argument("--pause", type=float, default=0.0, help="sleep between submits")
    ap.add_argument("--retries", type=int, default=4, help="attempts per file on 429/5xx/network")
    ap.add_argument("--max-retry-sleep", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    tokens = [t.strip() for t in args.token.split(",") if t.strip()] if args.token else []
    if not args.dry_run and not tokens:
        ap.error("--token (or BSI_API_TOKEN) is required unless --dry-run")

    max_bytes = args.max_mb * 1024 * 1024
    os.makedirs(args.tmpdir, exist_ok=True)
    scratch = os.path.join(args.tmpdir, "current.ifc")

    # ---- resume state -----------------------------------------------------
    done: set[str] = set()
    if args.state and os.path.exists(args.state):
        with open(args.state) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("ok") and rec.get("key"):
                    done.add(rec["key"])
        log(f"resume: {len(done)} member(s) already submitted", verbose=True)

    state_fh = open(args.state, "a", buffering=1) if args.state else None
    log_fh = open(args.log, "a", buffering=1) if args.log else None

    api = None if args.dry_run else [Api(args.url, t, args.timeout) for t in tokens]
    log(f"using {len(tokens)} token(s)"
        + (" - per-user locks are independent, so this is the parallelism width"
           if len(tokens) > 1 else " - single user, expect ~25-30 files/hour"),
        verbose=True) if not args.dry_run else None

    stop = {"flag": False}

    def _sigint(signum, frame):
        stop["flag"] = True
        print("\n[interrupt] finishing current file, then stopping...", flush=True)

    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    counters = dict(seen=0, candidates=0, submitted=0, skipped_done=0, skipped_big=0,
                    skipped_other=0, failed=0, bytes_up=0, throttled=0)
    started = time.time()

    def emit(rec: dict):
        if log_fh:
            log_fh.write(json.dumps(rec) + "\n")
        if state_fh and rec.get("ok"):
            state_fh.write(json.dumps(rec) + "\n")

    log(f"opening {args.tar} (streaming single pass)")
    tf = tarfile.open(args.tar, mode="r|gz")

    index = -1
    try:
        for member in tf:
            index += 1
            counters["seen"] += 1

            if stop["flag"]:
                break
            if index < args.start_index:
                continue
            if not member.isfile():
                continue

            kind, upload_name = classify(member.name)
            if kind is None:
                counters["skipped_other"] += 1
                continue

            key = f"{index}:{member.name}"
            if key in done:
                counters["skipped_done"] += 1
                continue

            counters["candidates"] += 1

            # pre-check the size when the tar header gives it to us (plain members)
            if kind == "plain" and member.size > max_bytes:
                counters["skipped_big"] += 1
                log(f"SKIP too large ({member.size/1048576:.1f} MB) {member.name}", verbose=True)
                emit({"ts": iso_now(), "key": key, "name": member.name, "index": index,
                      "ok": False, "reason": "too_large", "size": member.size})
                continue

            # ---- extract exactly one member --------------------------------
            src = tf.extractfile(member)
            if src is None:
                counters["skipped_other"] += 1
                continue

            written = 0
            too_big = False
            try:
                with open(scratch, "wb") as out:
                    stream = gzip.GzipFile(fileobj=src) if kind == "gzip" else src
                    try:
                        while True:
                            buf = stream.read(CHUNK)
                            if not buf:
                                break
                            written += len(buf)
                            if written > max_bytes:
                                too_big = True
                                break
                            out.write(buf)
                    finally:
                        if kind == "gzip":
                            stream.close()
                        src.close()
            except Exception as exc:
                # A truncated/corrupt member must not abort the whole run.
                counters["skipped_other"] += 1
                log(f"SKIP unreadable member {member.name}: {type(exc).__name__}: {exc}",
                    verbose=True)
                emit({"ts": iso_now(), "key": key, "name": member.name, "index": index,
                      "ok": False, "reason": "unreadable",
                      "error": f"{type(exc).__name__}: {exc}"})
                if os.path.exists(scratch):
                    os.unlink(scratch)
                continue

            if too_big or written == 0:
                os.unlink(scratch)
                reason = "too_large" if too_big else "empty"
                counters["skipped_big" if too_big else "skipped_other"] += 1
                log(f"SKIP {reason} {member.name}", verbose=True)
                emit({"ts": iso_now(), "key": key, "name": member.name, "index": index,
                      "ok": False, "reason": reason, "size": written})
                continue

            if args.dry_run:
                log(f"DRY-RUN would submit {upload_name} ({written/1048576:.2f} MB) "
                    f"from {member.name}", verbose=True)
                counters["submitted"] += 1
                os.unlink(scratch)
                emit({"ts": iso_now(), "key": key, "name": member.name, "upload_name": upload_name,
                      "index": index, "ok": True, "dry_run": True, "size": written})
                if args.limit and counters["submitted"] >= args.limit:
                    break
                continue

            # ---- upload with retries ---------------------------------------
            # rotate users round-robin so the per-user redis locks are independent
            client = api[counters["candidates"] % len(api)]
            attempt = 0
            status = None
            body_text = ""
            public_id = None
            while attempt < args.retries and not stop["flag"]:
                attempt += 1
                try:
                    status, _hdr, body_text, retry_after = client.post_file(scratch, upload_name)
                except Exception as exc:  # network/timeout
                    status, retry_after = -1, None
                    body_text = f"{type(exc).__name__}: {exc}"

                if status == 201:
                    break
                if status in (429, 500, 502, 503, 504, -1):
                    if status == 429:
                        counters["throttled"] += 1
                    wait = retry_after if retry_after else min(2 ** attempt * 5, args.max_retry_sleep)
                    wait = min(wait, args.max_retry_sleep)
                    log(f"  {status} on {upload_name}; retry {attempt}/{args.retries} in {wait:.0f}s",
                        verbose=True)
                    # sleep in small steps so SIGINT stays responsive
                    end = time.time() + wait
                    while time.time() < end and not stop["flag"]:
                        time.sleep(min(1.0, end - time.time()))
                    continue
                break  # 4xx other than 429 -> not retryable

            if status == 201:
                try:
                    public_id = json.loads(body_text).get("public_id")
                except Exception:
                    public_id = None
                counters["submitted"] += 1
                counters["bytes_up"] += written
                log(f"OK   [{counters['submitted']:>6}] {upload_name} "
                    f"({written/1048576:.2f} MB) -> {public_id}")
                emit({"ts": iso_now(), "key": key, "name": member.name, "upload_name": upload_name,
                      "index": index, "ok": True, "size": written, "status": status,
                      "public_id": public_id})
                if args.limit and counters["submitted"] >= args.limit:
                    os.unlink(scratch)
                    break
            else:
                counters["failed"] += 1
                log(f"FAIL [{counters['failed']:>6}] {upload_name} status={status} "
                    f"{body_text[:300]}", verbose=True)
                emit({"ts": iso_now(), "key": key, "name": member.name, "upload_name": upload_name,
                      "index": index, "ok": False, "reason": f"http_{status}", "size": written,
                      "body": body_text[:1000]})

            os.unlink(scratch)

            if args.pause:
                time.sleep(args.pause)

    except (KeyboardInterrupt, BrokenPipeError):
        log("interrupted")
    finally:
        tf.close()
        if state_fh:
            state_fh.close()
        if log_fh:
            log_fh.close()
        if os.path.exists(scratch):
            os.unlink(scratch)

    elapsed = time.time() - started
    log("---- summary ----")
    log(f"members seen          {counters['seen']}")
    log(f"candidates (.ifc/.gz) {counters['candidates']}")
    log(f"submitted             {counters['submitted']} ({counters['bytes_up']/1073741824:.2f} GiB)")
    log(f"already done / skipped {counters['skipped_done']}")
    log(f"skipped too large     {counters['skipped_big']}")
    log(f"skipped other         {counters['skipped_other']}")
    log(f"failed                {counters['failed']}")
    log(f"throttled (429) hits  {counters['throttled']}")
    log(f"elapsed               {elapsed/60:.1f} min")
    if counters["submitted"] and elapsed > 0:
        log(f"throughput            {counters['submitted']/(elapsed/3600):.0f} files/hour")
    log(f"last member index     {index}  (use --start-index {index+1} to resume past it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
