import json
import subprocess
import sys
import textwrap
import ifcopenshell
from .. import TaskContext, logger

from apps.ifc_validation_models.models import ModelInstance

from django.db import transaction

_completion_script_str = textwrap.dedent(
    """
    import sys
    import json
    import ifcopenshell

    file_path, step_ids = json.load(sys.stdin)
    ifc_file = ifcopenshell.open(file_path)
    json.dump([ifc_file[step_id].is_a() for step_id in step_ids], sys.stdout)
    """
)


def _obtain_ifc_types(file_path: str, step_ids: list[int]) -> list[str]:
    return json.loads(subprocess.run(
        [sys.executable, "-u", "-c", _completion_script_str],
        input=json.dumps([file_path, step_ids]),
        capture_output=True,
        text=True,
        check=True,
    ).stdout)


def process_instance_completion(context:TaskContext):
    # the current task doesn't have any execution layer and links instance ids to outcomes
    model_id = context.request.model.id
    model_instances = ModelInstance.objects.filter(model_id=model_id, ifc_type__in=[None, ''])
    instance_count = model_instances.count()
    logger.info(f'Retrieved {instance_count:,} ModelInstance record(s)')

    step_ids = list(
        model_instances.values_list("stepfile_id", flat=True)
    )
    step_id_to_type = dict(zip(step_ids, _obtain_ifc_types(context.file_path, step_ids)))

    with transaction.atomic():
        for inst in model_instances.iterator():
            inst.ifc_type = step_id_to_type[inst.stepfile_id]
            inst.save()

    return f'Updated {instance_count:,} ModelInstance record(s)'
