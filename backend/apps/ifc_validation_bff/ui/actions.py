import re

from django.db import transaction

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation.tasks import ifc_file_validation_task
from .build import can_delete


def enqueue_validation(request_id, file_name):
    ifc_file_validation_task.delay(request_id, file_name)


def upload_files(files, policy):
    errors = []
    if not files:
        errors.append("Select at least one IFC file to validate.")
    if len(files) > policy.max_files:
        errors.append(f"Upload at most {policy.max_files} files at a time.")
    for file in files:
        if not file.name.lower().endswith(".ifc"):
            errors.append(f"{file.name}: only .ifc files can be uploaded.")
        if file.size > policy.max_size_mb * 1024 * 1024:
            errors.append(f"{file.name}: file exceeds the {policy.max_size_mb} MB size limit.")
    if errors:
        return tuple(errors)
    with transaction.atomic():
        for file in files:
            item = ValidationRequest.objects.create(file=file, file_name=file.name, size=file.size, channel="WEBUI")
            transaction.on_commit(lambda id=item.id, name=item.file_name: enqueue_validation(id, name))
    return ()


def delete_files(user, public_ids):
    ids = tuple(dict.fromkeys(public_ids))
    if not ids:
        return ("Select at least one IFC file to delete.",)
    if any(not re.fullmatch(r"r\d{1,20}", id) for id in ids):
        return ("The selected IFC file could not be found.",)
    with transaction.atomic():
        items = list(ValidationRequest.objects.select_for_update().filter(
            created_by=user, deleted=False, pk__in=[ValidationRequest.to_private_id(id) for id in ids]))
        if len(items) != len(ids):
            return ("The selected IFC file could not be found.",)
        if any(not can_delete(item.status, item.progress) for item in items):
            return ("Unable to delete your IFC file as it is still being processed.",)
        for item in items:
            item.delete()
            from ..report.pdf import remove_pdf
            remove_pdf(item)
    return ()
