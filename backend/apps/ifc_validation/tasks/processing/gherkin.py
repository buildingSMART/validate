from apps.ifc_validation_models.models import Model

from .. import TaskContext, logger, with_model

def process_gherkin_outcomes(context:TaskContext):
    with with_model(context.request.id) as model:
        # @gh todo, actually write gherkin results to DB here, currently in gherkin environment.py
        status_field = context.config.status_field.name
        agg_status = context.task.determine_aggregate_status()
        setattr(model, status_field, agg_status)
        model.save(update_fields=[status_field])
        
        return f'agg_status = {Model.Status(agg_status).label}\nraw_output = {context.result}' 
    
def process_normative_ia(context:TaskContext):
    return process_gherkin_outcomes(context)

def process_normative_ip(context:TaskContext):
    return process_gherkin_outcomes(context)

def process_prerequisites(context:TaskContext):
    return process_gherkin_outcomes(context)

def process_industry_practices(context:TaskContext):
    return process_gherkin_outcomes(context)