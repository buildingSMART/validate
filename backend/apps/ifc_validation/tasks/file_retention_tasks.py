from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.management import call_command

from core.utils import log_execution


logger = get_task_logger(__name__)


@shared_task(bind=True)
@log_execution
def archive_files(self, *args, **kwargs):
    call_command("archive_files", **kwargs)


@shared_task(bind=True)
@log_execution
def remove_files(self, *args, **kwargs):
    call_command("remove_files", **kwargs)