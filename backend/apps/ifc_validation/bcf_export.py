"""
Experimental export of Validation Outcomes to BCF 2.1 (BIM Collaboration Format).

One BCF topic is created per error/warning outcome, mirroring what the report UI
shows: outcomes are grouped per rule/constraint and capped at MAX_OUTCOMES_PER_RULE
per group (with the total count mentioned in the topic description when capped).

Where the offending entity has an IFC GlobalId (stored in ModelInstance.fields by
the instance completion task), the topic gets a viewpoint selecting that element.
For non-rooted entities (e.g. IfcPolyline) the nearest parent IfcProduct is looked
up in the IFC file, when it is still available on disk.

Requires the 'bcf-client' package (https://pypi.org/project/bcf-client/).
"""
import json
import logging
import os
import re
import struct
import tempfile
import zlib
from collections import defaultdict

from django.conf import settings

from apps.ifc_validation_models.models import ValidationOutcome, ValidationRequest, ValidationTask
from apps.ifc_validation_models.models import calculate_whitelist

logger = logging.getLogger(__name__)

BCF_AUTHOR = "validate@buildingsmart.org"

MAX_TITLE_LENGTH = 100

GHERKIN_TASK_TYPES = (
    ValidationTask.Type.NORMATIVE_IA,
    ValidationTask.Type.NORMATIVE_IP,
    ValidationTask.Type.PREREQUISITES,
    ValidationTask.Type.INDUSTRY_PRACTICES,
)

RELEVANT_TASK_TYPES = (
    ValidationTask.Type.SCHEMA,
    ValidationTask.Type.SYNTAX,
    ValidationTask.Type.HEADER_SYNTAX,
    ValidationTask.Type.HEADER,
) + GHERKIN_TASK_TYPES

FILE_LEVEL_LABELS = {
    ValidationTask.Type.SYNTAX: "Syntax error",
    ValidationTask.Type.HEADER_SYNTAX: "Header syntax error",
    ValidationTask.Type.HEADER: "Header policy",
}

SEVERITY_TO_TOPIC_TYPE = {
    ValidationOutcome.OutcomeSeverity.ERROR: "Error",
    ValidationOutcome.OutcomeSeverity.WARNING: "Warning",
}


def _placeholder_snapshot_png(width=320, height=240, rgb=(226, 232, 240)) -> bytes:
    # Sommige viewers (o.a. BIMcollab ZOOM) activeren een viewpoint alleen via de
    # snapshot-thumbnail; zonder PNG geldt het viewpoint daar als afwezig.
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag, data):
        payload = tag + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


_SNAPSHOT_PNG = _placeholder_snapshot_png()

# XML 1.0 does not allow most C0 control characters, even escaped; lone surrogates
# crash on save and ￾/￿ are non-characters — bcf-client does not guard these
INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")

# IFC GlobalIds are 22 chars from a base64 alphabet including $ and _
IFC_GUID_PATTERN = re.compile(r"[0-9A-Za-z_$]{22}")


def _sanitize(value: str) -> str:
    return INVALID_XML_CHARS.sub("", value)


def _is_valid_ifc_guid(guid) -> bool:
    return isinstance(guid, str) and IFC_GUID_PATTERN.fullmatch(guid) is not None


def _format_value(value) -> str:
    """Formats an expected/observed JSON value (str, dict, list, number) for display."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def _group_key(outcome, task_type):
    """Grouping key per rule/constraint, identical to the titles used in the report UI."""
    if task_type == ValidationTask.Type.SCHEMA:
        try:
            parsed = json.loads(outcome.feature) if outcome.feature else {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        attribute = parsed.get("attribute") or "Uncategorized"
        constraint_type = parsed.get("type") or "Uncategorized"
        return f"{constraint_type.replace('_', ' ').capitalize()} - {attribute}"
    if task_type in FILE_LEVEL_LABELS:
        return FILE_LEVEL_LABELS[task_type]
    return outcome.feature or str(outcome.outcome_code)


def _walk_up_to_product(ifc_file, entity, max_depth=8, max_visited=200):
    """Finds the nearest parent IfcProduct via inverse relationships (BFS), or None."""
    seen, queue = {entity.id()}, [(entity, 0)]
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth or len(seen) > max_visited:
            break
        for inverse in ifc_file.get_inverse(current):
            if inverse.id() in seen:
                continue
            seen.add(inverse.id())
            if inverse.is_a("IfcProduct"):
                return inverse
            queue.append((inverse, depth + 1))
    return None


def _open_ifc_file(ifc_path):
    if not ifc_path:
        return None
    try:
        import ifcopenshell
        return ifcopenshell.open(ifc_path)
    except Exception as err:
        # file may be removed by retention, or not parseable (syntax errors)
        logger.info(f"BCF export continues without parent-element lookup: {err}")
        return None


def generate_bcf(request: ValidationRequest, output_path: str, ifc_path: str = None) -> dict:
    """
    Generates a BCF 2.1 file for all error/warning outcomes of a Validation Request.

    Returns a stats dict: {'topics', 'with_viewpoint', 'via_parent', 'truncated_groups', 'skipped'}.
    """
    import numpy as np
    from bcf.v2.bcfxml import BcfXml
    from bcf.v2.visinfo import VisualizationInfoHandler

    # open the IFC lazily: only needed when a capped outcome lacks a usable GlobalId
    ifc_state = {"loaded": False, "file": None}

    def get_ifc_file():
        if not ifc_state["loaded"]:
            ifc_state["loaded"] = True
            ifc_state["file"] = _open_ifc_file(ifc_path)
        return ifc_state["file"]

    tasks = [
        task for task_type in RELEVANT_TASK_TYPES
        if (task := ValidationTask.objects.filter(request_id=request.id, type=task_type).last())
    ]

    # allowlist upgrades (to PASSED) are applied in SQL, not per row
    wl_annotations, effective_severity = calculate_whitelist(include_whitelist=True)

    # cap per group while iterating; only capped outcomes are kept in memory
    grouped = defaultdict(list)
    totals = defaultdict(int)
    for task in tasks:
        outcomes = (
            task.outcomes
            .annotate(**wl_annotations)
            .annotate(effective_severity=effective_severity)
            .filter(effective_severity__in=(
                ValidationOutcome.OutcomeSeverity.ERROR,
                ValidationOutcome.OutcomeSeverity.WARNING,
            ))
            .order_by("-severity_in_db", "id")  # errors fill the cap before warnings, like the report
            .select_related("instance")
        )
        for outcome in outcomes.iterator():
            key = (task.type, _group_key(outcome, task.type))
            totals[key] += 1
            if len(grouped[key]) < settings.MAX_OUTCOMES_PER_RULE:
                grouped[key].append(outcome)

    bcfxml = BcfXml.create_new(project_name=f"Validation report {_sanitize(request.file_name)}")

    stats = {"topics": 0, "with_viewpoint": 0, "via_parent": 0, "truncated_groups": 0, "skipped": 0}

    # deterministic order: errors before warnings, then per group title
    def sort_key(item):
        (_, group_title), outcomes = item
        return (-max(outcome.effective_severity for outcome in outcomes), group_title)

    for (task_type, group_title), capped in sorted(grouped.items(), key=sort_key):
        total = totals[(task_type, group_title)]
        if total > len(capped):
            stats["truncated_groups"] += 1
            stats["skipped"] += total - len(capped)

        for outcome in capped:
            severity_label = SEVERITY_TO_TOPIC_TYPE[outcome.effective_severity]
            instance = outcome.instance
            guid = (instance.fields or {}).get("GlobalId") if instance else None
            if not _is_valid_ifc_guid(guid):
                guid = None

            parent_note = None
            if instance and not guid and (ifc_file := get_ifc_file()) is not None:
                try:
                    parent = _walk_up_to_product(ifc_file, ifc_file[instance.stepfile_id])
                except Exception:
                    parent = None
                if parent is not None:
                    guid = parent.GlobalId
                    parent_note = (
                        f"The viewpoint selects the parent element {parent.is_a()} "
                        f"(#{parent.id()}, GlobalId {guid}) that contains the reported entity."
                    )
                    stats["via_parent"] += 1

            description_parts = []
            observed = _format_value(outcome.observed)
            if observed:
                description_parts.append(observed)
            expected = _format_value(outcome.expected)
            if expected:
                description_parts.append(f"Expected: {expected}")
            if instance:
                instance_guid = (instance.fields or {}).get("GlobalId")
                entity = f"Entity: {instance.ifc_type} (#{instance.stepfile_id}"
                entity += f", GlobalId {instance_guid})" if instance_guid else ")"
                description_parts.append(entity)
            if parent_note:
                description_parts.append(parent_note)
            if total > len(capped):
                description_parts.append(
                    f"Note: this issue occurs {total} times in the model; "
                    f"the first {len(capped)} occurrences are included in this BCF."
                )
            description_parts.append(
                f"Reported by the buildingSMART Validation Service "
                f"(report {request.public_id}, outcome {outcome.public_id}, {outcome.outcome_code})."
            )

            title = f"[{severity_label}] {group_title}"
            if len(title) > MAX_TITLE_LENGTH:
                title = title[: MAX_TITLE_LENGTH - 1] + "…"

            topic = bcfxml.add_topic(
                title=_sanitize(title),
                description=_sanitize("\n\n".join(description_parts)),
                author=BCF_AUTHOR,
                topic_type=severity_label,
                topic_status="Active",
            )
            if _is_valid_ifc_guid(guid):
                vi_handler = VisualizationInfoHandler.create_from_point_and_guids(np.zeros(3), guid)
                vi_handler.snapshot = _SNAPSHOT_PNG
                topic.add_visinfo_handler(vi_handler, f"{vi_handler.guid}.png")
                stats["with_viewpoint"] += 1
            stats["topics"] += 1

    # save atomically: a failing bcf-client save() clobbers an existing target file
    temp_path = output_path + ".tmp"
    bcfxml.save(temp_path)
    os.replace(temp_path, output_path)
    logger.info(f"BCF export for request {request.public_id}: {stats}")
    return stats


def generate_bcf_download(validation_request: ValidationRequest) -> tuple:
    """
    Generates the BCF file for a Validation Request and returns (file bytes, stats).

    Resolves the uploaded IFC file on disk when still available (it may be removed
    or archived by file retention), enabling parent-element lookup for viewpoints.
    """
    ifc_path = None
    if validation_request.file:
        candidate = os.path.join(settings.MEDIA_ROOT, validation_request.file.name)
        if os.path.exists(candidate):
            ifc_path = candidate

    with tempfile.TemporaryDirectory() as temp_dir:
        bcf_path = os.path.join(temp_dir, "report.bcf")
        stats = generate_bcf(validation_request, bcf_path, ifc_path=ifc_path)
        with open(bcf_path, "rb") as bcf_file:
            return bcf_file.read(), stats
