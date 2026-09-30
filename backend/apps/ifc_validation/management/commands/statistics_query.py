import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from apps.ifc_validation.statistics_query import (
    CONCEPT,
    QueryFilter,
    StatisticsAnnotation,
    StatisticsExpression,
    StatisticsQuery,
    StatisticsQueryBuilder,
    result_payload,
)

SPEC_DOCUMENTATION = """\
Reads a statistics query specification as JSON (from a file or stdin) and
prints the executed result as JSON, without going through the admin UI.

The specification mirrors the semantic query dataclasses:

{
  "source": "entity",
  "groups": ["schema"],
  "expression": {"function": "count_distinct", "operand_a": "model"},
  "ordering": "descending",
  "limit": 100,
  "filters": [
    {"concept": "schema", "operator": "eq", "value": "IFC4"},
    {"concept": "size_mb", "operator": "gt", "value": 5}
  ],
  "annotations": [
    {"name": "walls", "filters": [{"concept": "entity", "operator": "eq", "value": "IfcWall"}]}
  ]
}

String filter values are parsed with the concept vocabulary ('concrete',
'true', 'standard', ...) and non-negative integers become numbers; typed
JSON values (true, 5) are used as-is. The printed document contains the
result columns, rows, the number of models considered, and the SQL.
"""


def parse_filters(entries):
    filters = []
    for entry in entries:
        try:
            concept = CONCEPT[entry["concept"]]
        except KeyError as error:
            raise CommandError(
                f"Unknown filter concept {entry.get('concept')!r}.",
            ) from error
        value = entry["value"]
        if isinstance(value, str):
            try:
                value = concept.parse(value)
            except ValueError as error:
                raise CommandError(
                    f"Invalid value {entry['value']!r} for concept {concept.name!r}.",
                ) from error
        filters.append(QueryFilter(concept.name, entry["operator"], value))
    return tuple(filters)


def parse_annotations(entries):
    return tuple(
        StatisticsAnnotation(
            entry["name"],
            StatisticsExpression(**entry.get("expression", {})),
            parse_filters(entry.get("filters", ())),
        )
        for entry in entries
    )


class Command(BaseCommand):
    help = (
        "Execute a statistics query specification (JSON) and print the result "
        "as JSON. Internal export helper for one-off analysis tooling."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "spec",
            nargs="?",
            default="-",
            help="Path to a JSON specification file, or '-' for stdin (default).",
        )

    def handle(self, *args, **options):
        if options["spec"] == "-":
            raw = sys.stdin.read()
        else:
            try:
                raw = Path(options["spec"]).read_text()
            except OSError as error:
                raise CommandError(str(error)) from error
        try:
            spec = json.loads(raw)
        except json.JSONDecodeError as error:
            raise CommandError(f"Invalid JSON specification: {error}") from error

        spec.setdefault("source", None)
        if not spec["source"]:
            raise CommandError("The specification requires a 'source'.")
        query = StatisticsQuery(
            source=spec["source"],
            groups=tuple(spec.get("groups", ())),
            expression=StatisticsExpression(**spec.get("expression", {})),
            ordering=spec.get("ordering", "descending"),
            limit=spec.get("limit", 10),
            filters=parse_filters(spec.get("filters", ())),
            annotations=parse_annotations(spec.get("annotations", ())),
        )
        try:
            result = StatisticsQueryBuilder(query).execute()
        except (ValueError, RuntimeError) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(json.dumps(result_payload(result), cls=DjangoJSONEncoder))
