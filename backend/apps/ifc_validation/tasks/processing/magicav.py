from .. import TaskContext, with_model
from apps.ifc_validation_models.models import Model


def process_magic_and_clamav(context:TaskContext):
    output, success, valid = (context.result.get(k) for k in ("output", "success", "valid"))
    
    with with_model(context.request.id) as model:
        agg_status = Model.Status.VALID if valid else Model.Status.INVALID
        setattr(model, context.config.status_field.name, agg_status)

        model.save(update_fields=[context.config.status_field.name])
        return f'Magic and av check completed: {output} success = {success} valid = {valid}'
