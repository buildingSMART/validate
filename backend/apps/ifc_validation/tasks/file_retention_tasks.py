from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.management import call_command

from core.utils import log_execution


logger = get_task_logger(__name__)


@shared_task(bind=True)
@log_execution
def apply_file_retention(self, *args, **kwargs):
    call_command("apply_file_retention", **kwargs)