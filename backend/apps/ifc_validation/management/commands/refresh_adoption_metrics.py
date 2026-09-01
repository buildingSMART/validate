"""Refresh the fact table behind the "Implementer Adoption" Grafana dashboard.

Why a fact table: the capability panel ("which functional parts do tools
actually produce") aggregates ifc_validation_outcome, a 150M-row table with no
index on `created`. One month is seconds, twelve months in one statement times
out. So this command computes one month per statement -- translating the month
into a validation_task id range, which the index can use -- and stores the
result at a granularity the dashboard can still aggregate over any window:

    month x functional_part x tool_stem x company_id -> number of models

Distinct counts over a range are then taken by the panel itself (a distinct
over 12 months is NOT the sum of 12 monthly distincts). The table is a few
hundred rows per month.

"Activated" means the outcome severity is anything but N/A (executed, passed,
warning or error): a failed alignment rule still proves the tool writes
alignment. This is a lower bound - a rule only activates when its precondition
is met.

tool_stem is the authoring tool name up to the first digit ("Revit 26.4 (ENU)"
-> "Revit"), because the name field carries version and language package.
Replace with canonical_name once migration 0035 (IVS-884) is on PROD.

Each month runs in its own transaction, so a timeout on one month does not
lose the others. Safe to re-run; months are deleted and re-inserted.

Cron (manager node, nightly), see docker/prometheus/prod-crons/refresh_adoption_metrics.sh:
    30 2 * * *  /home/prd-root/validation-service/docker/prometheus/prod-crons/refresh_adoption_metrics.sh
"""
import json
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

TABLE = "vs_adoption_capability"

DDL = [
    f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        month           date        NOT NULL,
        functional_part text        NOT NULL,
        tool_stem       text        NOT NULL,
        company_id      integer,
        models          integer     NOT NULL,
        computed_at     timestamptz NOT NULL DEFAULT now()
    )""",
    f"CREATE INDEX IF NOT EXISTS {TABLE}_month_idx ON {TABLE} (month)",
]

# Month boundaries expressed as validation_task id ranges (ids are monotonic).
SQL_BOUNDS = """
SELECT date_trunc('month', created)::date AS month, min(id) AS lo, max(id) AS hi
FROM ifc_validation_task
WHERE created >= date_trunc('month', now()) - make_interval(months => %s)
GROUP BY 1
ORDER BY 1
"""

TOOL_STEM = r"COALESCE(NULLIF(regexp_replace(at.name, '\s*[0-9][0-9.]*.*$', ''), ''), '(unknown)')"

SQL_FACTS = f"""
SELECT %s::date                     AS month,
       left(vo.feature, 3)          AS functional_part,
       {TOOL_STEM}                  AS tool_stem,
       at.company_id                AS company_id,
       COUNT(DISTINCT m.id)         AS models
FROM ifc_validation_outcome vo
JOIN ifc_validation_task    vt ON vt.id = vo.validation_task_id
JOIN ifc_validation_request vr ON vr.id = vt.request_id
JOIN ifc_model              m  ON m.id  = vr.model_id
LEFT JOIN ifc_authoring_tool at ON at.id = m.produced_by_id
WHERE vo.validation_task_id >= %s
  AND vo.validation_task_id <  %s
  AND vo.severity > 0
  AND vo.feature ~ '^[A-Z]{{3}}[0-9]{{3}}'
GROUP BY 1, 2, 3, 4
"""


class Command(BaseCommand):

    help = (
        f"Recompute the last N months of {TABLE}, the fact table behind the "
        "'Implementer Adoption' Grafana dashboard. One statement per month.\n"
        "\n"
        "  python manage.py refresh_adoption_metrics                 # last 13 months\n"
        "  python manage.py refresh_adoption_metrics --months 24\n"
        "  python manage.py refresh_adoption_metrics --dry-run       # compute, print, write nothing\n"
        "  python manage.py refresh_adoption_metrics --out /tmp/adoption.json\n"
    )

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=13,
                            help="How many months back to (re)compute, current month included (default 13).")
        parser.add_argument("--statement-timeout", type=int, default=900,
                            help="Per-month statement timeout in seconds (default 900).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Run the month queries and print row counts, but create/write nothing.")
        parser.add_argument("--out", default=None,
                            help="Also write the computed facts to this JSON file.")

    def handle(self, *args, **options):
        months = options["months"]
        timeout_ms = options["statement_timeout"] * 1000
        dry_run = options["dry_run"]
        out_path = options["out"]

        with connection.cursor() as c:
            if dry_run:
                c.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            else:
                for stmt in DDL:
                    c.execute(stmt)
            c.execute(SQL_BOUNDS, [months - 1])
            bounds = c.fetchall()

        self.stdout.write(f"{'DRY RUN - ' if dry_run else ''}{len(bounds)} month(s), "
                          f"timeout {options['statement_timeout']}s per month")

        collected = []
        failed = []
        t_all = time.time()
        for month, lo, hi in bounds:
            t0 = time.time()
            try:
                with transaction.atomic():
                    with connection.cursor() as c:
                        c.execute("SET LOCAL statement_timeout = %s", [timeout_ms])
                        if dry_run:
                            c.execute(SQL_FACTS, [month, lo, hi + 1])
                            rows = c.fetchall()
                            n = len(rows)
                        else:
                            c.execute(f"DELETE FROM {TABLE} WHERE month = %s", [month])
                            c.execute(
                                f"INSERT INTO {TABLE} (month, functional_part, tool_stem, company_id, models) "
                                + SQL_FACTS, [month, lo, hi + 1])
                            n = c.rowcount
                            rows = []
                            if out_path:
                                c.execute(f"SELECT month, functional_part, tool_stem, company_id, models "
                                          f"FROM {TABLE} WHERE month = %s", [month])
                                rows = c.fetchall()
                self.stdout.write(f"  {month}  tasks {lo}-{hi}  {n:5d} fact rows  {time.time() - t0:6.1f}s")
                collected.extend(rows)
            except Exception as err:  # timeout or SQL error: report and continue with the next month
                failed.append(str(month))
                self.stderr.write(f"  {month}  FAILED after {time.time() - t0:.1f}s: {str(err).splitlines()[0]}")

        self.stdout.write(f"done in {time.time() - t_all:.0f}s"
                          + (f", FAILED months: {', '.join(failed)}" if failed else ""))

        if out_path:
            with open(out_path, "w") as f:
                json.dump([{"month": str(m), "functional_part": fp, "tool_stem": ts,
                            "company_id": cid, "models": n}
                           for m, fp, ts, cid, n in collected], f, indent=1)
            self.stdout.write(f"written: {out_path} ({len(collected)} rows)")

        if failed:
            raise SystemExit(1)
