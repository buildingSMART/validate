#!/bin/bash
# DB health gauges for the Validation Service, exposed via the node_exporter
# textfile collector. Cron: every 15 min.
#
# Route: this script -> Grafana datasource proxy (/api/ds/query, SELECT only)
#        -> Postgres. The DB password stays inside Grafana.
# NOTE:  datasource uid is hardcoded below (DEV: "devpg") -- adjust per env.
# Cost:  one ~40 ms query; deliberately nothing on ifc_validation_outcome (~5M rows).
#
# Gauges: vs_requests_stuck (>1h old, not done, not FAILED -- same definition
#   as the "Stuck requests" panel), vs_tasks_initiated_total,
#   vs_requests_soft_deleted_total, vs_requests_total, vs_queue_wait_p95_1h,
#   vs_db_health_scrape_success, vs_db_health_last_run_timestamp_seconds.
# On a failed run only the two self-metrics are written (success=0), so the
# content gauges go stale in Prometheus instead of repeating old values.
set -uo pipefail

GRAFANA_URL=${GRAFANA_URL:-http://127.0.0.1:3000}
# No password fallback on purpose: a wrong default here once broke the cron
# silently (scrape_success stayed 0). Pass GRAFANA_AUTH=user:password in the
# cron line, or better an env file the cron sources.
GRAFANA_AUTH=${GRAFANA_AUTH:?set GRAFANA_AUTH to user:password for the Grafana API}
TEXTFILE_DIR=${TEXTFILE_DIR:?set TEXTFILE_DIR to the node_exporter textfile directory, e.g. TEXTFILE_DIR=/data/srv/textfile}
OUT="$TEXTFILE_DIR/vs_db_health.prom"
TMP="$OUT.$$.tmp"
NOW=$(date +%s)

mkdir -p "$TEXTFILE_DIR"

# Eén round-trip; subselects zijn elk goedkoop (geïndexeerde status/created/
# deleted-kolommen; request-tabel ~4k rijen, task-tabel klein).
SQL="SELECT
  (SELECT COUNT(*) FROM ifc_validation_request
    WHERE completed IS NULL AND status NOT IN ('COMPLETED','FAILED')
      AND created < NOW() - INTERVAL '1 hour')                AS requests_stuck,
  (SELECT COUNT(*) FROM ifc_validation_task
    WHERE status = 'INITIATED')                               AS tasks_initiated,
  (SELECT COUNT(*) FROM ifc_validation_request WHERE deleted) AS requests_soft_deleted,
  (SELECT COUNT(*) FROM ifc_validation_request)               AS requests_total,
  (SELECT COALESCE(percentile_cont(0.95) WITHIN GROUP
            (ORDER BY EXTRACT(EPOCH FROM ft.fs - r.created)), 0)
     FROM ifc_validation_request r
     JOIN LATERAL (SELECT MIN(t.started) AS fs FROM ifc_validation_task t
                    WHERE t.request_id = r.id) ft ON ft.fs IS NOT NULL
    WHERE r.created > NOW() - INTERVAL '1 hour')              AS queue_wait_p95_1h"

if BODY=$(python3 - "$GRAFANA_URL" "$GRAFANA_AUTH" "$SQL" <<'PY'
import base64, json, sys, urllib.request

url, auth, sql = sys.argv[1], sys.argv[2], sys.argv[3]
payload = json.dumps({
    "queries": [{"refId": "A", "datasource": {"uid": "devpg"},
                 "rawSql": sql, "format": "table"}],
    "from": "now-5m", "to": "now",
}).encode()
req = urllib.request.Request(
    url + "/api/ds/query", data=payload,
    headers={"Content-Type": "application/json",
             "Authorization": "Basic " + base64.b64encode(auth.encode()).decode()})
try:
    resp = json.load(urllib.request.urlopen(req, timeout=25))
except Exception as exc:  # korte melding; geen traceback in cron-mail
    sys.exit(f"ds/query onbereikbaar: {exc}")
result = resp["results"]["A"]
if result.get("status") != 200 or not result.get("frames"):
    sys.exit("ds/query gaf geen 200/frames: " + json.dumps(result)[:300])
frame = result["frames"][0]
names = [f["name"] for f in frame["schema"]["fields"]]
row = dict(zip(names, (col[0] for col in frame["data"]["values"])))

def fmt(v):
    if v is None:
        sys.exit("NULL in resultaat: " + json.dumps(row))
    f = float(v)
    return str(int(f)) if f.is_integer() else f"{f:.3f}"

HELP = {
    "vs_requests_stuck": "Requests ouder dan 1u die niet af zijn (completed IS NULL, status niet COMPLETED/FAILED). Hoort 0 te zijn.",
    "vs_tasks_initiated_total": "Validatietaken die op status INITIATED staan (gauge, momentopname). Blijvend hoge waarde = orphans (F1).",
    "vs_requests_soft_deleted_total": "Soft-deleted validatierequests (gauge, momentopname).",
    "vs_requests_total": "Alle validatierequests, inclusief soft-deleted (gauge, momentopname).",
    "vs_queue_wait_p95_1h": "p95 wachttijd in seconden tussen aanmelden en start eerste taak, requests uit het laatste uur; 0 als er geen waren.",
}
KEYMAP = {
    "vs_requests_stuck": "requests_stuck",
    "vs_tasks_initiated_total": "tasks_initiated",
    "vs_requests_soft_deleted_total": "requests_soft_deleted",
    "vs_requests_total": "requests_total",
    "vs_queue_wait_p95_1h": "queue_wait_p95_1h",
}
out = []
for metric, col in KEYMAP.items():
    out.append(f"# HELP {metric} {HELP[metric]}")
    out.append(f"# TYPE {metric} gauge")
    out.append(f"{metric} {fmt(row[col])}")
print("\n".join(out))
PY
); then
  SUCCESS=1
else
  echo "db_health_metrics: query mislukt, schrijf alleen zelf-metrics" >&2
  SUCCESS=0
  BODY=""
fi

{
  [ -n "$BODY" ] && printf '%s\n' "$BODY"
  echo "# HELP vs_db_health_scrape_success 1 als de laatste run van db_health_metrics.sh slaagde, 0 zo niet."
  echo "# TYPE vs_db_health_scrape_success gauge"
  echo "vs_db_health_scrape_success $SUCCESS"
  echo "# HELP vs_db_health_last_run_timestamp_seconds Unixtijd van de laatste run (geslaagd of niet)."
  echo "# TYPE vs_db_health_last_run_timestamp_seconds gauge"
  echo "vs_db_health_last_run_timestamp_seconds $NOW"
} > "$TMP"

# atomisch vervangen, zodat node_exporter nooit een half bestand leest
mv "$TMP" "$OUT"
chmod 644 "$OUT"
