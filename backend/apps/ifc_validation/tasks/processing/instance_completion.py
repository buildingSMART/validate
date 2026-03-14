import json
import subprocess
import sys
import textwrap
from typing import Any
import ifcopenshell
from .. import TaskContext, logger

from apps.ifc_validation_models.models import ModelInstance

from django.db import transaction

_completion_script_str = textwrap.dedent(
    """
    import sys
    import json
    import ifcopenshell
    import itertools
    import functools

    file_path, step_ids = file_path, step_ids = json.load(sys.stdin)
    ifc_file = ifcopenshell.open(file_path)
    def filter_serializable(v):
        def inner(k, v):
            if k == "type":
                return None
            elif isinstance(v, (list, tuple)):
                v = list(filter(lambda w: w is not None, map(functools.partial(inner, k), v)))
            elif isinstance(v, ifcopenshell.entity_instance):
                return None
            if v:
                return k, v
        return dict(filter(None, itertools.starmap(inner, v.items())))
    json.dump([(ifc_file[step_id].is_a(), filter_serializable(ifc_file[step_id].get_info(include_identifier=False))) for step_id in step_ids], sys.stdout)
    """
)


def _obtain_ifc_types_and_args(file_path: str, step_ids: list[int]) -> list[tuple[str, dict[str, Any]]]:
    proc = subprocess.run(
        [sys.executable, "-u", "-c", _completion_script_str],
        input=json.dumps([file_path, step_ids]),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        logger.error(proc.stderr)
        raise RuntimeError(f"Subprocess exited with code {proc.returncode}")
    return json.loads(proc.stdout)


def process_instance_completion(context:TaskContext):
    # the current task doesn't have any execution layer and links instance ids to outcomes
    model_id = context.request.model.id
    model_instances = ModelInstance.objects.filter(model_id=model_id, ifc_type__in=[None, ''])
    instance_count = model_instances.count()
    logger.info(f'Retrieved {instance_count:,} ModelInstance record(s)')

    step_ids = list(
        model_instances.values_list("stepfile_id", flat=True)
    )
    step_id_to_type_and_attrs = dict(zip(step_ids, _obtain_ifc_types_and_args(context.file_path, step_ids)))

    with transaction.atomic():
        for inst in model_instances.iterator():
            inst.ifc_type, inst.fields = step_id_to_type_and_attrs[inst.stepfile_id]
            inst.save()

    return f'Updated {instance_count:,} ModelInstance record(s)'
