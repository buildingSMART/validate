import contextlib
import functools
import os

from django.db import transaction

from core.utils import log_execution
from celery.utils.log import get_task_logger

from apps.ifc_validation_models.settings import MEDIA_ROOT
from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation_models.models import ValidationRequest, Model

logger = get_task_logger(__name__)

@log_execution
@requires_django_user_context
@transaction.atomic
# @requires_django_exclusive_table_lock(Model, 'EXCLUSIVE')
# --> table lock, slower - DO NOT USE
def get_or_create_ifc_model(request_id):

    id = request_id
    request = ValidationRequest.objects.get(pk=id)
    if request.model is None:

        # acquire row lock (... uses "FOR UPDATE" hint)
        request = ValidationRequest.objects.select_for_update().get(pk=id)

        model, _ = Model.objects.get_or_create(
            file_name=request.file_name,
            file=request.file,
            size=request.file.size,
            uploaded_by=request.created_by
        )
        request.model = model
        request.save()

        return model

    else:
        return request.model
    
    
@contextlib.contextmanager
def with_model(request_id):
    with transaction.atomic():
        yield get_or_create_ifc_model(request_id)


@functools.lru_cache(maxsize=1024)
def get_absolute_file_path(file_name):

    """
    Resolves the absolute file path of an uploaded file and checks if it exists.
    It tries resolving Django MEDIA_ROOT and current working directory, and caches the result.

    Mandatory Args:
       file_name: relative file name of the uploaded file.

    Returns:
       Absolute file path of the uploaded file.
    """

    ifc_fn = os.path.join(MEDIA_ROOT, file_name)

    if not os.path.exists(ifc_fn):
        ifc_fn2 = os.path.join(os.getcwd(), ifc_fn)
        if not os.path.exists(ifc_fn2):
            raise FileNotFoundError(f"File path for file_name={file_name} was not found (tried loading '{ifc_fn}' and '{ifc_fn2}').")

    ifc_fn = os.path.abspath(ifc_fn)

    logger.debug(f"get_absolute_file_path(): file_name={file_name} returned '{ifc_fn}'")
    return ifc_fn