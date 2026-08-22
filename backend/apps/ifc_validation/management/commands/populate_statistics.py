from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Exists, OuterRef, Q

from apps.ifc_validation.checks.statistics.apply_mvd import available_template_names
from apps.ifc_validation.tasks.statistics_tasks import (
    missing_template_names,
    populate_entity_count_histogram,
    populate_pset_count_histogram,
    populate_template_statistics,
)
from apps.ifc_validation_models.models import (
    EntityCountHistogram,
    Model,
    PsetCountHistogram,
)


class Command(BaseCommand):
    help = "Populate all missing statistics for up to N eligible models."

    statistic_tasks = (
        ("entity histogram", populate_entity_count_histogram),
        ("property-set histogram", populate_pset_count_histogram),
        ("template statistics", populate_template_statistics),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "count",
            type=int,
            help="Maximum number of models to process.",
        )

    def handle(self, *args, **options):
        count = options["count"]
        if count < 1:
            raise CommandError("count must be greater than zero")

        template_names = available_template_names()
        completed_entity_histograms = EntityCountHistogram.objects.filter(
            model_id=OuterRef("pk"),
            count=EntityCountHistogram.COMPLETION_MARKER_COUNT,
        )
        completed_pset_histograms = PsetCountHistogram.objects.filter(
            model_id=OuterRef("pk"),
            count=PsetCountHistogram.COMPLETION_MARKER_COUNT,
        )
        annotations = {
            "has_entity_histogram": Exists(completed_entity_histograms),
            "has_pset_histogram": Exists(completed_pset_histograms),
        }
        incomplete = (
            Q(has_entity_histogram=False)
            | Q(has_pset_histogram=False)
        )
        if template_names:
            annotations["completed_template_count"] = Count(
                "template_statistics__template_name",
                filter=Q(
                    template_statistics__graph__isnull=True,
                    template_statistics__template_name__in=template_names,
                ),
                distinct=True,
            )
            incomplete |= Q(completed_template_count__lt=len(template_names))

        models = list(
            Model.objects.annotate(
                **annotations,
            )
            .filter(incomplete)
            .exclude(file="")
            .distinct()
            .order_by("pk")
            [:count]
        )

        failures = []
        totals = {label: 0 for label, _ in self.statistic_tasks}
        for model in models:
            pending_tasks = []
            if not model.has_entity_histogram:
                pending_tasks.append((
                    "entity histogram",
                    populate_entity_count_histogram,
                    (model.pk,),
                ))
            if not model.has_pset_histogram:
                pending_tasks.append((
                    "property-set histogram",
                    populate_pset_count_histogram,
                    (model.pk,),
                ))
            missing_templates = missing_template_names(model, template_names)
            if missing_templates:
                pending_tasks.append((
                    "template statistics",
                    populate_template_statistics,
                    (model.pk, missing_templates),
                ))

            for label, task, task_arguments in pending_tasks:
                try:
                    totals[label] += task.run(*task_arguments)
                except Exception as error:
                    failures.append((model.pk, label))
                    self.stderr.write(
                        self.style.ERROR(f"Model {model.pk}, {label}: {error}")
                    )

        summary = ", ".join(
            f"{value} {label} result(s)" for label, value in totals.items()
        )
        self.stdout.write(self.style.SUCCESS(
            f"Processed {len(models)} model(s); {summary}."
        ))

        if failures:
            formatted_failures = ", ".join(
                f"{model_id} ({label})" for model_id, label in failures
            )
            raise CommandError(
                f"Failed to populate {len(failures)} statistic task(s): "
                f"{formatted_failures}"
            )
