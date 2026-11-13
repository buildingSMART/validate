from __future__ import annotations

import re
from itertools import groupby
from typing import TYPE_CHECKING

from ..datamodel.report import (
    DigitalSignature,
    FileMetadata,
    HeaderValidation,
    OutcomeSeverity,
    TaskReport,
    ReportKind,
    GherkinDescription,
    GherkinGroup,
    GherkinResult,
    SchemaGroup,
    SchemaResult,
    Section,
    SyntaxError,
)
from .value_formatting import coerce_to_text, interpret_rule_value, outer_whitespace, pretty_file_size, truncate

if TYPE_CHECKING:
    from ..datamodel.report import OutcomeInput, ReportInput

REPORT_TITLES = {
    "file": "File Info",
    "syntax": "STEP Syntax Report",
    "schema": "IFC Schema Report",
    "normative": "Normative IFC Rules Report",
    "industry": "Industry Practices Report",
}


def build_report(data: ReportInput, kind: ReportKind, *, include_all=True, prioritize_findings=False) -> TaskReport:
    if prioritize_findings:
        data = data.outcomes_sorted()
    elif kind == "schema":
        data = data.outcomes_sorted(key=lambda outcome: -outcome.severity_after_whitelisting)
    if kind in ("schema", "normative", "industry"):
        data = data.outcomes_grouped()

    def outcome_groups():
        for title, outcomes in groupby(data.outcomes, key=lambda outcome: outcome.group_title):
            original = tuple(outcomes)
            visible = tuple(outcome for outcome in original
                            if include_all or outcome.severity_after_whitelisting >= OutcomeSeverity.WARNING)
            if visible:
                yield title, visible[:data.outcome_limit], len(original)

    def header_validation() -> HeaderValidation:
        def text(key: str, fallback: str = "-") -> str:
            value = data.header.get(key)
            if isinstance(value, (tuple, list)):
                return " ".join(map(str, value))
            return str(value) if value else fallback

        return HeaderValidation(
            schema_identifier=text("schema_identifier"),
            model_view_definition=text("mvd"),
            file_name=text("name"),
            time_stamp=text("time_stamp"),
            originating_system=text("originating_system"),
            preprocessor_version=text("preprocessor_version"),
            company_name=outer_whitespace(data.header.get("company_name")),
            application_name=outer_whitespace(data.header.get("application_name")),
            application_version=outer_whitespace(data.header.get("version")),
            author=text("author"),
            organization=text("organization"),
            invalid_fields=frozenset(data.header.get("validation_errors") or ()),
        )

    def syntax() -> Section[SyntaxError]:
        def error(outcome: OutcomeInput) -> SyntaxError:
            observed = outcome.observed or ""
            position = re.match(r"^On line (\d+) column (\d+).*", observed)
            message = f"expected: {outcome.expected}, observed: {outcome.observed}" if outcome.expected is not None else observed
            lines = message.split("\n")
            return SyntaxError(
                **severity(outcome),
                line_number=int(position[1]) if position else None,
                column_number=int(position[2]) if position else None,
                diagnosis="\n".join(lines[:-2]),
                source_excerpt="\n".join(lines[-2:]),
            )

        return Section(
            data.status,
            tuple(
                error(outcome)
                for outcome in data.outcomes
                if not prioritize_findings or outcome.severity_after_whitelisting >= OutcomeSeverity.WARNING
            ),
        )

    def schema() -> Section[SchemaGroup]:
        def describe(outcome: OutcomeInput):
            if outcome.task_type == "PREREQ":
                # The prerequisites are gherkin-based checks that are rendered in the schema report -
                # which otherwise consists of outputs that come from ifcopenshell.validate
                description = re.sub(r"^IFC\d{3}\s*-\s*", "", outcome.feature or "")
                observed = coerce_to_text(outcome.observed)
                if (description and (isinstance(outcome.expected, (tuple, list)) or outcome.expected)
                        and (isinstance(outcome.observed, (tuple, list)) or outcome.observed)):
                    message = f"Description: {description} ,  Expected: {coerce_to_text(outcome.expected)}, Observed: {observed}"
                else:
                    message = f"{description}\n{observed}" if outcome.feature else observed
                return observed.split("\n")[0] or None, message
            if not outcome.feature and outcome.severity_in_db == OutcomeSeverity.PASSED:
                return None, coerce_to_text(outcome.observed)

            constraint = outcome.schema_feature.get("type")
            message = coerce_to_text(outcome.observed)
            subcaption = message.split("\n")[0] or None if constraint != "schema" else None
            return subcaption, "\n".join(message.split("\n")[2:]) if constraint != "schema" else message

        def result(outcome: OutcomeInput) -> SchemaResult:
            return SchemaResult(**severity(outcome), instance=outcome.instance, message=describe(outcome)[1])

        return Section(
            data.status,
            tuple(
                group(
                    title,
                    tuple(map(result, outcomes)),
                    count,
                    subcaption=describe(outcomes[0])[0],
                )
                for title, outcomes, count in outcome_groups()
            ),
        )

    def gherkin() -> Section[GherkinGroup]:
        def result(outcome: OutcomeInput) -> GherkinResult:
            return GherkinResult(
                **severity(outcome),
                instance=outcome.instance,
                expected=interpret_rule_value(outcome.expected),
                observed=interpret_rule_value(outcome.observed),
            )

        return Section(
            data.status,
            tuple(
                group(
                    title,
                    tuple(map(result, outcomes)),
                    count,
                    gherkin=data.rules.get(title[:6], GherkinDescription(None, None)),
                )
                for title, outcomes, count in outcome_groups()
            ),
        )

    def signatures() -> tuple[DigitalSignature, ...]:
        def signature(value: dict) -> DigitalSignature:
            def text(key):
                found = value.get(key)
                return (str(found) if prioritize_findings else truncate(str(found))) if found else None

            return DigitalSignature(
                verification=value.get("signature", "valid_known_cert"),
                issuer=text("issuer"),
                subject=text("subject"),
                hash_algorithm=text("signature_hash_algorithm_name"),
                rsa_key_size=value.get("rsa_key_size"),
                valid_until=text("not_valid_after"),
                valid_from=text("not_valid_before"),
                fingerprint=text("fingerprint_hex"),
                payload=text("payload"),
                start=value.get("start"),
                end=value.get("end"),
            )

        return tuple(signature(o.observed) for o in data.outcomes if isinstance(o.observed, dict))

    match kind:
        case "syntax":
            section = syntax()
        case "schema":
            section = schema()
        case "normative" | "industry":
            section = gherkin()
        case _:
            section = None

    return TaskReport(
        request_id=data.request_id,
        kind=kind,
        title=REPORT_TITLES[kind],
        metadata=FileMetadata(data.file_name, pretty_file_size(data.size_bytes), data.created.strftime("%Y-%m-%d %H:%M:%S")),
        header=header_validation(),
        section=section,
        signatures=signatures() if kind == "file" else (),
    )


def severity(outcome: OutcomeInput) -> dict:
    return dict(severity_in_db=outcome.severity_in_db, allowlisted=outcome.allowlisted)


def group(title, results, count, *, subcaption=None, gherkin=None):
    """Build a result group and its visibility flags read by the templates.

    - Determine the highest visible severity, defaulting to not applicable.
    - Preserve the supplied occurrence count and flag omitted results.
    - Show the occurrence count when visible warnings/errors exist.
    - Flag source availability and return a GherkinGroup or SchemaGroup
      propagating gherkin description or subcaption info passed from the outside
    """
    highest = max((r.severity_after_whitelisting for r in results), default=OutcomeSeverity.NOT_APPLICABLE)
    common = dict(
        title=title,
        results=results,
        occurrence_count=count,
        severity_after_whitelisting=highest,
        show_occurrence_count=highest >= OutcomeSeverity.WARNING,
        is_truncated=count > len(results),
        show_source=any(r.instance and r.instance.source for r in results),
    )
    return GherkinGroup(**common, gherkin=gherkin) if gherkin is not None else SchemaGroup(**common, subcaption=subcaption)
