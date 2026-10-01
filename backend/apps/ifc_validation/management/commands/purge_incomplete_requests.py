"""
Hard-delete everything that is not a fully completed validation.

Targets every Validation Request whose status is not COMPLETED (PENDING,
INITIATED, FAILED and any stray value - including soft-deleted ones). For each
targeted request its Model, Validation Tasks/Outcomes and the uploaded file
(django-cleanup) are removed as well, so that the database ends up mirroring
only fully completed validations.

Completed requests and models are never touched. Dry-run by default; pass
--confirm to actually delete.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.ifc_validation_models.models import (
    Model,
    ValidationOutcome,
    ValidationRequest,
    ValidationTask,
)


class Command(BaseCommand):
    help = (
        "Hard-delete Validation Requests that are not COMPLETED, together with "
        "their Model, Tasks, Outcomes and uploaded files. Dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually delete; without this flag the command only reports.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report only (default behaviour; cannot be combined with --confirm).",
        )
        parser.add_argument(
            "--status",
            action="append",
            default=None,
            choices=[
                ValidationRequest.Status.PENDING,
                ValidationRequest.Status.INITIATED,
                ValidationRequest.Status.FAILED,
            ],
            help="Restrict to a specific non-completed status (repeatable).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Requests per delete batch (default 100).",
        )

    def handle(self, *args, **options):
        if options["confirm"] and options["dry_run"]:
            raise CommandError("--confirm and --dry-run are mutually exclusive.")
        if options["batch_size"] < 1:
            raise CommandError("--batch-size must be greater than zero.")

        if options["status"]:
            requests = ValidationRequest.objects.filter(status__in=options["status"])
            target_description = f"status(es) {', '.join(options['status'])}"
        else:
            requests = ValidationRequest.objects.exclude(
                status=ValidationRequest.Status.COMPLETED,
            )
            target_description = "any status other than COMPLETED"

        request_count = requests.count()
        model_count = requests.exclude(model__isnull=True).count()
        task_count = ValidationTask.objects.filter(request__in=requests).count()
        outcome_count = ValidationOutcome.objects.filter(
            validation_task__request__in=requests,
        ).count()
        file_count = requests.filter(
            file__isnull=False,
        ).exclude(file="").count()

        self.stdout.write(
            f"target   : {target_description}\n"
            f"requests : {request_count}\n"
            f"models   : {model_count}\n"
            f"tasks    : {task_count}\n"
            f"outcomes : {outcome_count}\n"
            f"files    : {file_count} (removed from storage via django-cleanup)"
        )

        if not options["confirm"]:
            self.stdout.write(
                self.style.WARNING("Dry run only - pass --confirm to delete."),
            )
            return

        processed = 0
        while True:
            batch = list(
                requests.order_by("pk").values_list("pk", "model_id")[
                    :options["batch_size"]
                ]
            )
            if not batch:
                break
            request_ids = [request_id for request_id, _ in batch]
            model_ids = [model_id for _, model_id in batch if model_id is not None]
            if model_ids:
                # Deleting a Model cascades to its request, task/outcome rows and
                # every statistics table (histograms, instances, template stats).
                Model.objects.filter(pk__in=model_ids).delete()
            ValidationRequest.objects.filter(pk__in=request_ids).delete()
            processed += len(batch)
            self.stdout.write(f"deleted {processed}/{request_count} request(s)")

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {processed} request(s) and {model_count} model(s); "
            "only COMPLETED validations remain.",
        ))
