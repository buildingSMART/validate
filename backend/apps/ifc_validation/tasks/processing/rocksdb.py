
import json

from apps.ifc_validation_models.models import Model
from .. import TaskContext, with_model


def process_rocksdb_conversion(context:TaskContext):

    with with_model(context.request.id) as model:
        model.status_rocksdb_conversion = context.result
        model.save(update_fields=['status_rocksdb_conversion'])
        return f"agg_status = {Model.Status(context.result).label}\nmessages = {context.result}"
