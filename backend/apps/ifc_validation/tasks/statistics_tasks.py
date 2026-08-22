import csv
import functools
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import psutil
from celery import group, shared_task
from celery.utils.log import get_task_logger
from django.db.models import Count, Q

from core.utils import log_execution

from apps.ifc_validation.checks.statistics.apply_mvd import available_template_names
from apps.ifc_validation_models.models import (
    EntityCountHistogram,
    Model,
    ModelInstance,
    PsetCountHistogram,
    TemplateStatistic,
)

from .utils import get_absolute_file_path

logger = get_task_logger(__name__)

PSET_DEFINITIONS_ROOT = (
    Path(__file__).resolve().parent.parent
    / "checks"
    / "ifc_gherkin_rules"
    / "features"
    / "resources"
)


_ENTITY_HISTOGRAM_SCRIPT = textwrap.dedent(
    """
    import functools
    import json
    import sys
    from collections import Counter

    import ifcopenshell

    file_path = json.load(sys.stdin)
    ifc_file = ifcopenshell.open(file_path)
    schema_identifier = ifc_file.schema_identifier
    schema = ifcopenshell.schema_by_name(schema_identifier)

    @functools.cache
    def supertypes(entity_name):
        declaration = schema.declaration_by_name(entity_name)
        result = []
        while declaration:
            result.append(declaration.name())
            declaration = declaration.supertype()
        return tuple(result)

    counts = Counter()
    for instance in ifc_file:
        for index, entity_name in enumerate(supertypes(instance.is_a())):
            counts[(entity_name, index > 0)] += 1

    json.dump(
        {
            "schema_identifier": schema_identifier,
            "entries": [
                [entity_name, is_supertype, count]
                for (entity_name, is_supertype), count in sorted(counts.items())
            ],
        },
        sys.stdout,
    )
    """
)


_PSET_HISTOGRAM_SCRIPT = textwrap.dedent(
    """
    import json
    import sys
    from collections import Counter

    import ifcopenshell

    file_path = json.load(sys.stdin)
    ifc_file = ifcopenshell.open(file_path)
    counts = Counter()

    def property_definitions(value):
        if value.is_a() == "IfcPropertySetDefinitionSet":
            yield from value[0]
        else:
            yield value

    def pset_name(pset):
        is_predefined = False
        try:
            # ifc4 and higher
            is_predefined = pset.is_a("IfcPreDefinedPropertySet")
        except:
            # ifc2x3
            is_predefined = not pset.is_a("IfcPropertySet")
        return pset.is_a() if is_predefined else (pset.Name or "")

    for pset in ifc_file.by_type("IfcPropertySetDefinition"):
        counts[(None, pset_name(pset))] += 1

    for type_object in ifc_file.by_type("IfcTypeObject"):
        for pset in type_object.HasPropertySets or ():
            counts[(type_object.is_a(), pset_name(pset))] += 1

    for relationship in ifc_file.by_type("IfcRelDefinesByProperties"):
        for pset in property_definitions(relationship.RelatingPropertyDefinition):
            for related_object in relationship.RelatedObjects:
                counts[(related_object.is_a(), pset_name(pset))] += 1

    json.dump(
        {
            "schema_identifier": ifc_file.schema_identifier,
            "entries": [
                [entity_name, pset_name, count]
                for (entity_name, pset_name), count in sorted(
                    counts.items(),
                    key=lambda item: ((item[0][0] or ""), item[0][1]),
                )
            ],
        },
        sys.stdout,
    )
    """
)


_TEMPLATE_STATISTICS_SCRIPT = textwrap.dedent(
    """
    import json
    import sys

    from apps.ifc_validation.checks.statistics.apply_mvd import (
        extract_template_statistics,
    )

    file_path, template_names = json.load(sys.stdin)
    json.dump(
        extract_template_statistics(
            file_path,
            template_names=template_names,
        ),
        sys.stdout,
    )
    """
)


def _run_ifc_statistics_subprocess(script, payload):
    process = subprocess.run(
        [sys.executable, "-u", "-c", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        logger.error(process.stderr)
        raise RuntimeError(
            f"IFC statistics subprocess exited with code {process.returncode}",
        )
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("IFC statistics subprocess returned invalid JSON") from error


def extract_entity_histogram_in_subprocess(file_path):
    return _run_ifc_statistics_subprocess(_ENTITY_HISTOGRAM_SCRIPT, file_path)


def extract_pset_histogram_in_subprocess(file_path):
    return _run_ifc_statistics_subprocess(_PSET_HISTOGRAM_SCRIPT, file_path)


def extract_template_statistics_in_subprocess(file_path, template_names):
    return _run_ifc_statistics_subprocess(
        _TEMPLATE_STATISTICS_SCRIPT,
        [file_path, list(template_names)],
    )


def pset_resource_schema(schema_identifier):
    normalized = schema_identifier.upper()
    if normalized.startswith("IFC4X3"):
        return "IFC4X3"
    if normalized.startswith("IFC4"):
        return "IFC4"
    if normalized.startswith("IFC2X3"):
        return "IFC2X3"
    raise ValueError(
        f"No property-set definitions are available for {schema_identifier!r}",
    )


@functools.cache
def standardized_pset_names(schema_identifier):
    csv_path = (
        PSET_DEFINITIONS_ROOT
        / pset_resource_schema(schema_identifier)
        / "pset_definitions.csv"
    )
    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        return frozenset(
            row["Name"]
            for row in csv.DictReader(csv_file)
            if row.get("Name")
        )


def missing_template_names(model, template_names=None):
    if template_names is None:
        template_names = available_template_names()
    completed = set(
        model.template_statistics.filter(
            graph__isnull=True,
            template_name__in=template_names,
        ).values_list("template_name", flat=True)
    )
    return tuple(name for name in template_names if name not in completed)


@shared_task
@log_execution
def populate_entity_count_histogram(model_id):
    model = Model.objects.get(pk=model_id)
    extracted = extract_entity_histogram_in_subprocess(
        get_absolute_file_path(model.file),
    )
    schema_identifier = extracted["schema_identifier"]
    entries = [
        EntityCountHistogram(
            model=model,
            entity_index=EntityCountHistogram.index_from_string(
                schema_identifier,
                entity_name,
            ),
            count=count,
            is_supertype=is_supertype,
        )
        for entity_name, is_supertype, count in extracted["entries"]
    ]

    model.histogram_entries.all().delete()
    EntityCountHistogram.objects.bulk_create([
        *entries,
        EntityCountHistogram.completion_marker(model),
    ])
    return len(entries)


@shared_task
@log_execution
def populate_pset_count_histogram(model_id):
    model = Model.objects.get(pk=model_id)
    extracted = extract_pset_histogram_in_subprocess(
        get_absolute_file_path(model.file),
    )
    schema_identifier = extracted["schema_identifier"]
    standardized_names = standardized_pset_names(schema_identifier)
    entries = [
        PsetCountHistogram(
            model=model,
            entity_index=(
                EntityCountHistogram.index_from_string(
                    schema_identifier,
                    entity_name,
                )
                if entity_name is not None else None
            ),
            pset_name=pset_name,
            is_standardized=pset_name in standardized_names,
            count=count,
        )
        for entity_name, pset_name, count in extracted["entries"]
    ]

    model.pset_count_entries.all().delete()
    PsetCountHistogram.objects.bulk_create([
        *entries,
        PsetCountHistogram.completion_marker(model),
    ])
    return len(entries)


@shared_task
@log_execution
def populate_template_statistics(model_id, template_names):
    model = Model.objects.get(pk=model_id)
    template_names = tuple(template_names)
    extracted = extract_template_statistics_in_subprocess(
        get_absolute_file_path(model.file),
        template_names,
    )

    model.template_statistics.filter(
        template_name__in=template_names,
    ).delete()
    matches = []
    for result in extracted:
        focus_instance, _ = ModelInstance.objects.get_or_create(
            model=model,
            stepfile_id=result["focus_step_id"],
            defaults={"ifc_type": result["focus_ifc_type"]},
        )
        matches.append(TemplateStatistic(
            model=model,
            template_name=result["template"],
            focus_instance=focus_instance,
            graph=result["graph"],
        ))

    TemplateStatistic.objects.bulk_create(matches)
    TemplateStatistic.objects.bulk_create([
        TemplateStatistic.completion_marker(model, template_name)
        for template_name in template_names
    ])
    return len(matches)


@shared_task
@log_execution
def schedule_model_statistic_tasks(batch_size=100, cpu_threshold=50):
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    if not 0 <= cpu_threshold <= 100:
        raise ValueError("cpu_threshold must be between 0 and 100")

    cpu_percent = psutil.cpu_percent(interval=1.0)
    if cpu_percent >= cpu_threshold:
        logger.info(
            "Skipping model statistics: CPU usage %.1f%% is at or above %.1f%%",
            cpu_percent,
            cpu_threshold,
        )
        return 0

    entity_model_ids = list(
        Model.objects
        .exclude(
            histogram_entries__count=EntityCountHistogram.COMPLETION_MARKER_COUNT,
        )
        .exclude(file="")
        .distinct()
        .order_by("pk")
        .values_list("pk", flat=True)[:batch_size]
    )

    pset_model_ids = list(
        Model.objects
        .exclude(
            pset_count_entries__count=PsetCountHistogram.COMPLETION_MARKER_COUNT,
        )
        .exclude(file="")
        .distinct()
        .order_by("pk")
        .values_list("pk", flat=True)[:batch_size]
    )

    template_names = available_template_names()
    if template_names:
        template_models = list(
            Model.objects
            .exclude(file="")
            .annotate(
                completed_template_count=Count(
                    "template_statistics__template_name",
                    filter=Q(
                        template_statistics__graph__isnull=True,
                        template_statistics__template_name__in=template_names,
                    ),
                    distinct=True,
                ),
            )
            .filter(completed_template_count__lt=len(template_names))
            .order_by("pk")[:batch_size]
        )
    else:
        template_models = []

    tasks = [
        *(populate_entity_count_histogram.s(model_id) for model_id in entity_model_ids),
        *(populate_pset_count_histogram.s(model_id) for model_id in pset_model_ids),
        *(
            populate_template_statistics.s(
                model.pk,
                missing_template_names(model, template_names),
            )
            for model in template_models
        ),
    ]
    if not tasks:
        return 0

    group(tasks).apply_async()
    logger.info(
        "Submitted %d model statistic task(s) at %.1f%% CPU usage",
        len(tasks),
        cpu_percent,
    )
    return len(tasks)
