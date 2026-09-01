import json
import os
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection


SQL_WEEK = """\
WITH base_models AS (
  SELECT DISTINCT m.id
  FROM ifc_model m
  LEFT JOIN ifc_user_additional_info uai
    ON uai.user_id = m.uploaded_by_id
  WHERE
    m.schema ILIKE %(schema)s
    AND m.created >= %(from_date)s
    AND m.created <  %(to_date)s
    AND COALESCE(uai.is_vendor, FALSE) = FALSE
),
failing_features AS (
  SELECT
    SPLIT_PART(vo.feature, ' ', 1) AS rule_code,
    COUNT(DISTINCT vr.model_id) AS models_failing
  FROM ifc_validation_outcome vo
  JOIN ifc_validation_task vt
    ON vt.id = vo.validation_task_id
  JOIN ifc_validation_request vr
    ON vr.id = vt.request_id
  WHERE
    vr.model_id IN (SELECT id FROM base_models)
    AND vo.severity = 4
    AND vo.feature IS NOT NULL
    AND SPLIT_PART(vo.feature, ' ', 1) ~ '^[A-Z]{3}[0-9]{3}$'
  GROUP BY SPLIT_PART(vo.feature, ' ', 1)
)
SELECT
  ff.rule_code,
  ff.models_failing,
  (SELECT COUNT(*) FROM base_models) AS total_models
FROM failing_features ff
ORDER BY ff.models_failing DESC;
"""


class Command(BaseCommand):

    help = (
        'Compute top failing validation rules per schema, '
        'batched in weekly windows to avoid overloading the database.\n'
        '\n'
        'Examples:\n'
        '\n'
        '  # Default: IFC4X3, weekly batches, top 20, from 2024-07-01 to today\n'
        '  docker compose exec backend python manage.py top_failing_rules\n'
        '\n'
        '  # Custom date range\n'
        '  docker compose exec backend python manage.py top_failing_rules --start 2025-01-01 --end 2026-01-01\n'
        '\n'
        '  # Different schema\n'
        '  docker compose exec backend python manage.py top_failing_rules --schema \'%%IFC2X3%%\'\n'
        '\n'
        '  # Larger batch windows if it\'s slow\n'
        '  docker compose exec backend python manage.py top_failing_rules --window 14\n'
        '\n'
        '  # Save results to a JSON file\n'
        '  docker compose exec backend python manage.py top_failing_rules --out /tmp/results.json\n'
    )

    def add_arguments(self, parser):

        parser.add_argument(
            '--schema',
            type=str,
            default='%IFC4X3%',
            help='Schema filter (SQL ILIKE pattern). Default: %%IFC4X3%%',
        )
        parser.add_argument(
            '--start',
            type=str,
            default='2024-07-01',
            help='Start date (YYYY-MM-DD). Default: 2024-07-01',
        )
        parser.add_argument(
            '--end',
            type=str,
            default=None,
            help='End date exclusive (YYYY-MM-DD). Default: today.',
        )
        parser.add_argument(
            '--window',
            type=int,
            default=7,
            help='Batch window size in days. Default: 7',
        )
        parser.add_argument(
            '--top',
            type=int,
            default=20,
            help='Number of top rules to show. Default: 20',
        )
        parser.add_argument(
            '--out',
            type=str,
            default=None,
            help='Output JSON file path (optional). If not set, prints to stdout.',
        )

    def handle(self, *args, **options):
        schema = options['schema']
        start = datetime.strptime(options['start'], '%Y-%m-%d').date()
        end = (
            datetime.strptime(options['end'], '%Y-%m-%d').date()
            if options['end']
            else datetime.now().date()
        )
        window = timedelta(days=options['window'])
        top_n = options['top']
        out_path = options['out']

        rule_failing = {}   # rule_code -> total models failing
        total_models = 0
        weeks_processed = 0

        current = start
        while current < end:
            next_date = min(current + window, end)

            self.stdout.write(f"  {current} -> {next_date} ...", ending="")

            with connection.cursor() as cursor:
                cursor.execute(SQL_WEEK, {
                    'schema': schema,
                    'from_date': current.isoformat(),
                    'to_date': next_date.isoformat(),
                })
                rows = cursor.fetchall()

            week_total = 0
            for rule_code, models_failing, week_models in rows:
                rule_failing[rule_code] = rule_failing.get(rule_code, 0) + models_failing
                week_total = max(week_total, week_models)

            total_models += week_total
            weeks_processed += 1
            self.stdout.write(f" {week_total} models, {len(rows)} rules")

            current = next_date

        # Build ranked result
        ranked = []
        for code, failing in sorted(rule_failing.items(), key=lambda x: -x[1]):
            pct = float(round(
                Decimal(100) * Decimal(failing) / Decimal(max(total_models, 1)),
                1
            ))
            ranked.append({
                'rule_code': code,
                'models_failing': failing,
                'total_models': total_models,
                'failure_rate_pct': pct,
            })

        ranked = ranked[:top_n]

        self.stdout.write("")
        self.stdout.write(
            f"Processed {weeks_processed} windows, "
            f"{total_models} total models, "
            f"{len(rule_failing)} distinct failing rules."
        )
        self.stdout.write("")

        # Table output
        self.stdout.write(f"{'#':<4} {'Rule':<10} {'Failing':>8} {'Total':>8} {'Rate':>8}")
        self.stdout.write("-" * 42)
        for i, r in enumerate(ranked, 1):
            self.stdout.write(
                f"{i:<4} {r['rule_code']:<10} {r['models_failing']:>8} "
                f"{r['total_models']:>8} {r['failure_rate_pct']:>7.1f}%"
            )

        if out_path:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(ranked, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\nWrote {out_path}"))
