import ifcopenshell
from .. import TaskContext, logger

from apps.ifc_validation_models.models import ModelInstance

from django.db import transaction 

def process_instance_completion(context:TaskContext):
    # the current task doesn't have any execution layer and links instance ids to outcomes
    ifc_file = ifcopenshell.open(context.rdb_file_path_if_exists)
    with transaction.atomic():
        model_id = context.request.model.id
        model_instances = ModelInstance.objects.filter(model_id=model_id, ifc_type__in=[None, ''])
        instance_count = model_instances.count()
        logger.info(f'Retrieved {instance_count:,} ModelInstance record(s)')
        
        for inst in model_instances.iterator():
            inst.ifc_type = ifc_file[inst.stepfile_id].is_a()
            inst.save()

        return f'Updated {instance_count:,} ModelInstance record(s)'
