from collections import Counter, defaultdict
from dataclasses import replace

from .build import build_report
from ..datamodel.report import CheckOverview, FullReport, ReportChapter


def build_full_report(inputs, *, generated_at, validation_state, tasks,
                      signature_status, security_status):
    def trim_schema(data):
        counts = Counter()

        def retain(outcome):
            key = (outcome.task_type, outcome.feature or '')
            counts[key] += 1
            return counts[key] <= data.outcome_limit

        ordered = data.outcomes_sorted().outcomes
        return data.with_outcomes(filter(retain, ordered))

    # Apply the schema cap before both overview counts and detail projection.
    inputs = {**inputs, 'schema': trim_schema(inputs['schema'])}
    reports = tuple(build_report(data, kind, prioritize_findings=True) for kind, data in inputs.items())

    def task_summary(task):
        reason = task.reason
        if task.status == 'Completed' and reason:
            reason = None if reason.startswith('agg_status =') else reason.splitlines()[0]
        return replace(task, reason=reason)

    def overview(report):
        data = inputs[report.kind]
        rules = defaultdict(Counter)
        for outcome in data.outcomes:
            rules[outcome.task_type, outcome.feature or ''][outcome.severity_after_whitelisting] += 1
        classifications = Counter(max(counts) for counts in rules.values())
        # Passing/executed rows never make a rule pass when it also has errors or warnings.
        return CheckOverview(
            title=report.title.removesuffix(' Report'), status=data.status,
            error_rules=classifications[4],
            error_outcomes=sum(counts[4] for counts in rules.values()),
            warning_rules=sum(counts[3] > 0 for counts in rules.values()),
            warning_outcomes=sum(counts[3] for counts in rules.values()),
            passed_rules=classifications[2] + classifications[1],
            not_applicable_rules=classifications[0],
        )

    def chapter(anchor, title, description, severities):
        def select(report):
            section = report.section
            if section and report.kind != 'syntax':
                # The group belongs to its most severe effective outcome. Do not
                # split one rule across chapters or derive check status from rows.
                groups = tuple(replace(group, results=tuple(sorted(group.results,
                    key=lambda result: -result.severity_after_whitelisting)))
                    for group in sorted(section.items, key=lambda group: (-group.severity_after_whitelisting, group.title))
                    if group.severity_after_whitelisting in severities)
                return replace(report, section=replace(section, items=groups)) if groups else None
            if section:
                errors = tuple(error for error in section.items if error.severity_after_whitelisting in severities)
                return replace(report, section=replace(section, items=errors)) if errors else None
            return None

        selected = tuple(filter(None, map(select, reports)))
        count = sum(len(report.section.items) for report in selected)
        return ReportChapter(anchor, title, description, selected, count)

    overview_rows = tuple(map(overview, reports[1:]))
    states = (inputs['file'].status, security_status, *(row.status for row in overview_rows))
    incomplete = validation_state != 'Completed' or any(status in ('n', 'p') for status in states)
    conformance = ('n' if incomplete else 'i' if 'i' in states or signature_status == 'i' or any(row.error_rules for row in overview_rows)
                   else 'w' if 'w' in states or reports[0].header.invalid_fields or any(row.warning_rules for row in overview_rows) else 'v')
    return FullReport(
        file=reports[0], generated_at=generated_at,
        conformance_status=conformance,
        header_status='w' if reports[0].header.invalid_fields and inputs['file'].status == 'v' else inputs['file'].status,
        signature_status=signature_status,
        overview=overview_rows,
        chapters=(
            chapter('findings', 'Errors', 'Error outcomes across all validation layers, ordered before warnings and passing rules.', (4,)),
            chapter('warnings', 'Warnings', 'Warning outcomes across all validation layers. A warning alone does not make an IFC file invalid.', (3,)),
            chapter('passed', 'Passed rules', 'Applicable rules without errors or warnings after allowlisting, including passed and executed outcomes.', (2, 1)),
            chapter('not-applicable', 'Not applicable rules', 'Rules explicitly recorded as not applicable to this model.', (0,)),
        ), tasks=tuple(map(task_summary, tasks)), outcome_limit=inputs['file'].outcome_limit,
    )
