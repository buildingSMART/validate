"""Report content, independent of Django, HTML cells, and JSON serialization.

Rows describe outcomes. Templates own columns, labels, links, and markup. Gherkin values
are primitives or named IFC concepts, never a universal display-cell hierarchy.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby, islice
from collections.abc import Callable, Iterable
from enum import IntEnum
from typing import Generic, Literal, TypeAlias, TypeVar

ReportKind = Literal["file", "syntax", "schema", "normative", "industry"]
CheckStatus = Literal["v", "i", "w", "n", "p", "-"]
Scalar: TypeAlias = str | int | float | bool
JSONValue: TypeAlias = Scalar | None | list["JSONValue"] | dict[str, "JSONValue"]


class OutcomeSeverity(IntEnum):
    """Classify validation outcomes from not applicable through error."""

    NOT_APPLICABLE = 0
    EXECUTED = 1
    PASSED = 2
    WARNING = 3
    ERROR = 4


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Locate an IFC statement within its STEP source file."""

    line_number: int
    statement: str


@dataclass(frozen=True, slots=True)
class IfcInstance:
    """Identify an IFC instance and its optional source location."""

    step_id: int
    entity: str
    source: SourceLocation | None = None


@dataclass(frozen=True, slots=True)
class AttributeValue:
    """Preserve an explicitly wrapped scalar attribute value."""

    value: Scalar


@dataclass(frozen=True, slots=True)
class AllowedValues:
    """Describe permitted values and their optional context."""

    values: tuple[str, ...]
    context: str | None = None


@dataclass(frozen=True, slots=True)
class EntityReference:
    """Name an IFC entity referenced by a Gherkin outcome."""

    name: str


@dataclass(frozen=True, slots=True)
class InstanceReference:
    """Describe an IFC instance referenced by a Gherkin outcome."""

    description: str


@dataclass(frozen=True, slots=True)
class SchemaIdentifier:
    """List schema identifiers expected or observed by a Gherkin check."""

    identifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GuidCharacters:
    """Describe expected GUID characters or invalid characters found in a GUID."""

    characters: str
    expected: bool
    guid: str | None


@dataclass(frozen=True, slots=True)
class GuidLength:
    """Describe the expected or observed length of a GUID."""

    length: int
    expected: bool
    guid: str | None


@dataclass(frozen=True, slots=True)
class AlignmentMeasurement:
    """Describe an alignment measurement and its supporting geometric details."""

    description: str
    details: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnrecognizedValue:
    """Preserve an unrecognized persisted value as JSON text."""

    json: str


GherkinValue: TypeAlias = (
    Scalar | AttributeValue | AllowedValues | EntityReference | InstanceReference
    | SchemaIdentifier | GuidCharacters | GuidLength | AlignmentMeasurement
    | UnrecognizedValue | None
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """Record original severity and derive the effective severity after allowlisting."""

    severity_in_db: OutcomeSeverity
    allowlisted: bool

    @property
    def severity_after_whitelisting(self) -> OutcomeSeverity:
        return OutcomeSeverity.PASSED if self.allowlisted else self.severity_in_db


@dataclass(frozen=True, slots=True, kw_only=True)
class SyntaxError(Outcome):
    """Describe a syntax diagnostic with its position and source excerpt."""

    line_number: int | None
    column_number: int | None
    diagnosis: str
    source_excerpt: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SchemaResult(Outcome):
    """Describe a schema validation result for an optional IFC instance."""

    instance: IfcInstance | None
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GherkinResult(Outcome):
    """Describe the expected and observed values of a Gherkin check."""

    instance: IfcInstance | None
    expected: GherkinValue
    observed: GherkinValue


@dataclass(frozen=True, slots=True)
class GherkinDescription:
    """Provide a Gherkin feature's explanation and documentation link."""

    text: str | None
    url: str | None


Result = TypeVar("Result", SchemaResult, GherkinResult)


@dataclass(frozen=True, slots=True)
class ResultGroup(Generic[Result]):
    """Collect related outcomes with their classification and occurrence information."""

    title: str
    results: tuple[Result, ...]
    occurrence_count: int
    severity_after_whitelisting: OutcomeSeverity
    show_occurrence_count: bool
    is_truncated: bool
    show_source: bool


@dataclass(frozen=True, slots=True)
class SchemaGroup(ResultGroup[SchemaResult]):
    """Group schema results beneath a constraint title and optional subcaption."""

    subcaption: str | None


@dataclass(frozen=True, slots=True)
class GherkinGroup(ResultGroup[GherkinResult]):
    """Group Gherkin results with their feature description."""

    gherkin: GherkinDescription


SectionItem = TypeVar("SectionItem", SyntaxError, SchemaGroup, GherkinGroup)


@dataclass(frozen=True, slots=True)
class Section(Generic[SectionItem]):
    """Pair a validation status with typed syntax diagnostics or result groups."""

    status: CheckStatus
    items: tuple[SectionItem, ...]


@dataclass(frozen=True, slots=True)
class FileMetadata:
    """Describe the uploaded file and its report date."""

    file_name: str
    file_size: str
    report_date: str


@dataclass(frozen=True, slots=True)
class HeaderValidation:
    """Expose named IFC header values and the fields that failed header policy checks."""

    schema_identifier: str
    model_view_definition: str
    file_name: str
    time_stamp: str
    originating_system: str
    preprocessor_version: str
    company_name: str
    application_name: str
    application_version: str
    author: str
    organization: str
    invalid_fields: frozenset[str]


@dataclass(frozen=True, slots=True)
class DigitalSignature:
    """Describe a digital signature, its verification result, and certificate details."""

    verification: str
    issuer: str | None
    subject: str | None
    hash_algorithm: str | None
    rsa_key_size: int | None
    valid_until: str | None
    valid_from: str | None
    fingerprint: str | None
    payload: str | None
    start: str | int | None
    end: str | int | None


@dataclass(frozen=True, slots=True)
class TaskReport:
    """Provide the content of one report kind for a web page or full-report chapter."""

    request_id: str
    kind: ReportKind
    title: str
    metadata: FileMetadata
    header: HeaderValidation
    section: Section[SyntaxError] | Section[SchemaGroup] | Section[GherkinGroup] | None
    signatures: tuple[DigitalSignature, ...]


@dataclass(frozen=True, slots=True)
class ReportOptions:
    """Select the web report's visibility filter and requested page."""

    include_all: bool = False
    page: int = 1


@dataclass(frozen=True, slots=True)
class ReportPagination:
    """Describe a selected range of syntax diagnostics or whole outcome groups."""

    options: ReportOptions
    total: int
    first: int
    last: int
    previous_page: int | None
    next_page: int | None

    @classmethod
    def for_count(cls, total: int, options: ReportOptions, page_size: int = 10) -> ReportPagination:
        """Calculate clamped page bounds for eligible groups or syntax diagnostics."""
        page = min(max(options.page, 1), max(1, (total + page_size - 1) // page_size))
        start = (page - 1) * page_size
        return cls(
            options=ReportOptions(include_all=options.include_all, page=page),
            total=total,
            first=start + 1 if total else 0,
            last=min(start + page_size, total),
            previous_page=page - 1 if page > 1 else None,
            next_page=page + 1 if start + page_size < total else None,
        )

    def with_report(self, report: TaskReport) -> ReportPage:
        """Attach a built task report to these page bounds without further selection."""
        return ReportPage(
            options=self.options,
            total=self.total,
            first=self.first,
            last=self.last,
            previous_page=self.previous_page,
            next_page=self.next_page,
            report=report,
        )


@dataclass(frozen=True, slots=True)
class ReportPage(ReportPagination):
    """Pair a built task report with its selected range and page navigation."""

    report: TaskReport


@dataclass(frozen=True, slots=True)
class CheckOverview:
    """Summarize a validation layer's status and classified rule and outcome counts."""

    title: str
    status: CheckStatus
    error_rules: int
    error_outcomes: int
    warning_rules: int
    warning_outcomes: int
    passed_rules: int
    not_applicable_rules: int


@dataclass(frozen=True, slots=True)
class ReportChapter:
    """Collect task reports belonging to one severity chapter of a full report."""

    anchor: str
    title: str
    description: str
    reports: tuple[TaskReport, ...]
    rule_count: int


@dataclass(frozen=True, slots=True)
class TaskSummary:
    """Summarize a validation task's execution status and diagnostic reason."""

    title: str
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class FullReport:
    """Combine file information, validation overviews, severity chapters, and task execution."""

    file: TaskReport
    generated_at: str
    conformance_status: CheckStatus
    header_status: CheckStatus
    signature_status: CheckStatus
    overview: tuple[CheckOverview, ...]
    chapters: tuple[ReportChapter, ...]
    tasks: tuple[TaskSummary, ...]
    outcome_limit: int


@dataclass(frozen=True, slots=True)
class OutcomeInput(Outcome):
    """Materialize a stored outcome with the raw values needed for report projection."""

    task_type: str
    feature: str | None
    expected: JSONValue
    observed: JSONValue
    instance: IfcInstance | None

    @property
    def schema_feature(self) -> dict[str, JSONValue]:
        """Decode the schema processor's constraint metadata, tolerating legacy invalid values."""
        try:
            feature = json.loads(self.feature) if self.feature else {}
            return feature if isinstance(feature, dict) else {}
        except json.JSONDecodeError:
            return {}

    @property
    def group_title(self) -> str:
        """Identify the displayed schema constraint or Gherkin feature used for grouping."""
        match self.task_type:
            case "PREREQ":
                return "Schema - Version"
            case "SCHEMA":
                if not self.feature and self.severity_in_db == OutcomeSeverity.PASSED:
                    return "Schema - Validation"
                feature = self.schema_feature
                constraint = (feature.get("type") or "uncategorized").replace("_", " ").capitalize()
                return f"{constraint} - {feature.get('attribute') or 'Uncategorized'}"
            case _:
                return self.feature or ""


@dataclass(frozen=True, slots=True)
class ReportInput:
    """Materialize one report kind's metadata, status, outcomes, and Gherkin descriptions."""

    request_id: str
    file_name: str
    size_bytes: int
    created: datetime
    header: dict[str, JSONValue]
    status: CheckStatus
    outcomes: tuple[OutcomeInput, ...]
    rules: dict[str, GherkinDescription]
    outcome_limit: int

    def with_outcomes(self, outcomes: Iterable[OutcomeInput]) -> ReportInput:
        """Copy the report input with a new flat outcome sequence and unchanged metadata."""
        return ReportInput(
            request_id=self.request_id,
            file_name=self.file_name,
            size_bytes=self.size_bytes,
            created=self.created,
            header=self.header,
            status=self.status,
            outcomes=tuple(outcomes),
            rules=self.rules,
            outcome_limit=self.outcome_limit,
        )

    def outcomes_sorted(self, *, key: Callable[[OutcomeInput], int | tuple[int, ...]] | None = None) -> ReportInput:
        """Return outcomes in severity order or the explicitly supplied order."""
        return self.with_outcomes(sorted(
            self.outcomes,
            key=key or (lambda outcome: (-outcome.severity_after_whitelisting, -outcome.severity_in_db)),
        ))

    def outcomes_grouped(self) -> ReportInput:
        """Make equal-title outcomes adjacent in a flat, title-ordered sequence for groupby."""
        return self.with_outcomes(sorted(self.outcomes, key=lambda outcome: outcome.group_title))

    def outcome_groups_paginated(
        self, kind: ReportKind, options: ReportOptions, page_size: int = 10,
    ) -> tuple[ReportInput, ReportPagination]:
        """Select whole visible groups from grouped input while preserving their original outcomes and counts."""
        match kind:
            case "file":
                return self, ReportPagination.for_count(0, options, page_size)
            case "syntax":
                groups = tuple((outcome,) for outcome in self.outcomes)
            case _:
                groups = tuple(tuple(outcomes) for _, outcomes in groupby(self.outcomes, key=lambda outcome: outcome.group_title))
                groups = tuple(group for group in groups if options.include_all or any(
                    outcome.severity_after_whitelisting >= OutcomeSeverity.WARNING for outcome in group
                ))
        pagination = ReportPagination.for_count(len(groups), options, page_size)
        start = (pagination.options.page - 1) * page_size
        return self.with_outcomes(
            outcome for group in islice(groups, start, start + page_size) for outcome in group
        ), pagination
