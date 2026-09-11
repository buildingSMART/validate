from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.files.storage import default_storage
from django.core.management import call_command

from core.utils import log_execution

from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation_models.models import ValidationRequest


logger = get_task_logger(__name__)


@shared_task(bind=True)
@log_execution
def apply_file_retention(self, *args, **kwargs):
    call_command("apply_file_retention", **kwargs)


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def remove_validated_file(self, *args, **kwargs):
    """Remove the uploaded file of a validation request from disk and the DB.

    Used by the foreground validation workflow when
    ``settings.IMMEDIATE_STATS_AND_CLEANUP`` is enabled, once every check that
    needs the file (including instance completion) has finished.
    """
    id = kwargs.get('id')
    if id is None:
        raise ValueError("Argument 'id' is required.")

    request = ValidationRequest.objects.get(pk=id)
    if request.file_removed is not None:
        return f"File already removed for validation request {id}"

    request.remove_file()

    return f"Removed file from validation request {id}"