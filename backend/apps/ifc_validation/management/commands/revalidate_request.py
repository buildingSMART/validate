import logging

from django.core.management.base import BaseCommand

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation.tasks.task_runner import ifc_file_validation_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    
    help = (
        'Revalidate a specific Validation Request by its ID. This command resets the status of the request and re-queues it for validation.',
        'Note: archived or deleted requests cannot be revalidated.'
    )

    def add_arguments(self, parser):
        
        parser.add_argument(
            '--validation_request_id', '-id',       
            type=int,
            required=True,
            help='ID of the Validation Request to revalidate.'
        )


    @requires_django_user_context
    def handle(self, *args, **options):
        id = options['validation_request_id']

        try:
            request = ValidationRequest.objects.get(id=id)
        except ValidationRequest.DoesNotExist:
            logger.error(f"Validation Request with id={id} not found.")
            return
        
        # don't requeue deleted/archived requests
        if request.deleted:
            logger.warning(f"Validation Request with id={id} is deleted and cannot be revalidated.")
            return
        
        if request.file == None or request.file_removed:
            logger.warning(f"Validation Request with id={id} is archived and cannot be revalidated.")
            return
        
        # reset status and requeue for validation
        request.mark_as_pending(reason='Resubmitted for processing via Django Management Command')
        if request.model:
            request.model.reset_status()
        ifc_file_validation_task.delay(request.id, request.file_name)
        logger.info(f"Task 'ifc_file_validation_task' re-submitted for id:{request.id} file_name: {request.file_name}")