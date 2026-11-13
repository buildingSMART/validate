"""Load ORM, configuration and file inputs for the HTML UI and reports."""
from __future__ import annotations

import os
import re
from dataclasses import replace

from django.conf import settings
from django.utils import timezone

from apps.ifc_validation_models.models import Model, ValidationOutcome, ValidationRequest, ValidationTask, WhiteListEntry
from ..report.gherkin_lookup import get_feature_description, get_feature_url
from ..status import status_combine
from ..step_lines import add_step_lines, can_view_step_lines
from ..ui.build import build_dashboard, can_delete
from .model_summary import ModelSummary
from .report import CheckStatus, GherkinDescription, IfcInstance, OutcomeInput, OutcomeSeverity, ReportInput, ReportKind, SourceLocation
from .ui import Allowlist, AllowlistEntry, AllowlistPattern, DashboardEntry, DashboardOptions, Shell, UploadPolicy, Viewer


def load_model_summary(request: ValidationRequest) -> ModelSummary:
    """Materialize metadata and combined check states for the HTML frontend.

    The legacy JSON projection remains in views_legacy.format_request. Keep its
    pending policy here too: a check that has not run remains pending while the
    request is unfinished, and cannot hide a warning or error from a sibling.
    """
    model = request.model
    unfinished = request.status not in (ValidationRequest.Status.COMPLETED, ValidationRequest.Status.FAILED)

    def status(attribute: str) -> CheckStatus:
        value = getattr(model, attribute) if model is not None else None
        return "p" if value is None else value

    def pending(value: CheckStatus) -> CheckStatus:
        return "p" if unfinished and value == "n" else value

    return ModelSummary(
        request_id=request.public_id,
        file_name=request.file_name,
        size_bytes=request.size,
        created=request.created,
        status=request.status,
        progress=request.progress,
        header=model.header_validation or {} if model is not None else {},
        header_status=pending(status("status_header")),
        signatures_status=pending(status("status_signatures")),
        security_status=pending(status("status_magic_clamav")),
        syntax_status=status_combine(
            status("status_syntax"), status("status_header_syntax"),
            allow_not_executed=request.status == ValidationRequest.Status.COMPLETED,
        ),
        schema_status=pending(status_combine(status("status_schema_calculated"), status("status_prereq"))),
        normative_status=pending(status_combine(status("status_ia_calculated"), status("status_ip_calculated"))),
        industry_status=pending(status("status_industry_practices")),
    )


def load_report(validation_request: ValidationRequest, kind: ReportKind, viewer=None, *, include_successful_syntax=False) -> ReportInput:
    """Read each selected task once, and fetch instances/allowlisting in bulk."""
    summary = load_model_summary(validation_request)
    model = validation_request.model
    task_types = {
        "file": (ValidationTask.Type.DIGITAL_SIGNATURES,),
        "schema": (ValidationTask.Type.SCHEMA, ValidationTask.Type.PREREQUISITES),
        "normative": (ValidationTask.Type.NORMATIVE_IA, ValidationTask.Type.NORMATIVE_IP),
        "industry": (ValidationTask.Type.INDUSTRY_PRACTICES,),
        "syntax": (),
    }[kind]
    if kind == "syntax" and include_successful_syntax:
        task_types = (ValidationTask.Type.HEADER_SYNTAX, ValidationTask.Type.SYNTAX)
    elif kind == "syntax" and model:
        if model.status_header_syntax == Model.Status.INVALID:
            task_types = (ValidationTask.Type.HEADER_SYNTAX,)
        elif model.status_syntax == Model.Status.INVALID:
            task_types = (ValidationTask.Type.SYNTAX,)

    latest = {}
    for task_type, task_id in validation_request.tasks.filter(type__in=task_types).order_by("-id").values_list("type", "id"):
        latest.setdefault(task_type, task_id)
    outcomes = list(
        ValidationOutcome.objects.filter(validation_task_id__in=latest.values())
        .with_effective_severity().select_related("instance", "validation_task")
        .order_by("validation_task_id", "id")
    )
    sources = {}
    if kind in ("schema", "normative", "industry") and outcomes and can_view_step_lines(viewer):
        sources = {
            o.instance.public_id: {"guid": f"#{o.instance.stepfile_id}", "type": o.instance.ifc_type}
            for o in outcomes if o.instance is not None
        }
        # add_step_lines enriches the sources dictionary with line information read from the model when still available
        add_step_lines(sources, validation_request)

    def finding(outcome) -> OutcomeInput:
        instance = outcome.instance
        source = sources.get(instance.public_id, {}) if instance else {}
        location = SourceLocation(source["line"], source["step_line"]) if source.get("step_line") else None
        return OutcomeInput(
            task_type=outcome.validation_task.type, feature=outcome.feature,
            severity_in_db=OutcomeSeverity(outcome.severity_in_db),
            allowlisted=outcome.effective_severity != outcome.severity_in_db,
            expected=outcome.expected, observed=outcome.observed,
            instance=IfcInstance(instance.stepfile_id, instance.ifc_type, location) if instance else None,
        )

    rule_codes = {o.feature[:6] for o in outcomes if o.feature} if kind in ("normative", "industry") else set()
    return ReportInput(
        request_id=summary.request_id, file_name=summary.file_name,
        size_bytes=summary.size_bytes, created=summary.created,
        header=summary.header,
        status={"syntax": summary.syntax_status, "schema": summary.schema_status,
                "normative": summary.normative_status, "industry": summary.industry_status,
                "file": summary.header_status}[kind],
        outcomes=tuple(map(finding, outcomes)),
        rules={code: GherkinDescription(get_feature_description(code), get_feature_url(code)) for code in rule_codes},
        outcome_limit=settings.MAX_OUTCOMES_PER_RULE,
    )


def upload_policy() -> UploadPolicy:
    from core.settings import MAX_FILES_PER_UPLOAD, MAX_FILE_SIZE_IN_MB
    return UploadPolicy(getattr(settings, "MAX_FILES_PER_UPLOAD", MAX_FILES_PER_UPLOAD),
                        getattr(settings, "MAX_FILE_SIZE_IN_MB", MAX_FILE_SIZE_IN_MB))


def load_shell(request, user, title: str, active_page: str) -> Shell:
    def viewer():
        if user is None:
            return None
        names = (user.first_name, user.last_name)
        return Viewer(" ".join(names).strip() or user.username, user.email,
                      "".join(name[:1] for name in names) or user.username[:1],
                      user.useradditionalinfo.is_vendor_self_declared is None)

    current = viewer()
    version, commit = os.environ.get("VERSION", ""), os.environ.get("GIT_COMMIT_HASH", "")
    return Shell(title, active_page, current, request.get_host().split(".")[0], version, commit)


def dashboard_options(query) -> DashboardOptions:
    def integer(name, default):
        try:
            return int(query.get(name, default))
        except (ValueError, TypeError):
            return default
    size = integer("per_page", 5)
    return DashboardOptions(max(1, integer("page", 1)), size if size in (5, 10, 25) else 5,
                            tuple(dict.fromkeys(query.getlist("selected"))))


def load_dashboard(user, options: DashboardOptions):
    from ..report.pdf import artifact_path

    requests = ValidationRequest.objects.filter(created_by=user, deleted=False)
    count = requests.count()
    options = replace(options, page=min(options.page, max(1, (count + options.per_page - 1) // options.per_page)))
    start = (options.page - 1) * options.per_page
    page = requests.select_related("model", "created_by", "model__produced_by").order_by("-created", "-id")[start:start + options.per_page]

    def materialize(item):
        summary = load_model_summary(item)
        ready = item.has_final_status and not item.file_removed and artifact_path(item).is_file()
        pending = bool(item.has_final_status and not item.file_removed and not ready and item.completed and
                       (timezone.now() - item.completed).total_seconds() < 300)
        return DashboardEntry(summary.request_id, summary.file_name, summary.created, summary.status, summary.progress,
                              summary.header_status, bool(summary.header.get("validation_errors")),
                              summary.signatures_status, summary.syntax_status, summary.schema_status,
                              summary.normative_status, summary.industry_status, ready, pending)

    ids = [ValidationRequest.to_private_id(id) for id in options.selected if re.fullmatch(r"r\d{1,20}", id)]
    selected = tuple(item.public_id for item in requests.filter(pk__in=ids).order_by("id") if can_delete(item.status, item.progress))
    return build_dashboard(tuple(map(materialize, page)), count, options, selected)


def load_allowlist() -> Allowlist:
    def humanize(value):
        return value.replace("__", " / ").replace("_", " ").split()[-1]
    return Allowlist(tuple(
        AllowlistEntry(entry.id, entry.description or f"Entry {entry.id}", tuple(
            AllowlistPattern(humanize(fragment.column), humanize(fragment.operation), fragment.right_hand_side or "")
            for fragment in entry.fragments.all()
        )) for entry in WhiteListEntry.objects.prefetch_related("fragments").order_by("id")
    ))
