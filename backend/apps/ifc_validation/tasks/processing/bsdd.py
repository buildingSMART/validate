
import json

from apps.ifc_validation_models.models import Model, ValidationOutcome
from .. import TaskContext, logger, with_model


def process_bsdd(context:TaskContext):

    with with_model(context.request.id) as model:

        # update Validation Outcomes
        json_output = json.loads(context.result)
        for message in json_output['messages']:

            outcome = context.task.outcomes.create(
                severity=[c[0] for c in ValidationOutcome.OutcomeSeverity.choices if c[1] == (message['severity'])][0],
                outcome_code=[c[0] for c in ValidationOutcome.ValidationOutcomeCode.choices if c[1] == (message['outcome'])][0],
                observed=message['message'],
                feature=json.dumps({
                    'rule': message['rule'] if 'rule' in message else None,
                    'category': message['category'] if 'category' in message else None,
                    'dictionary': message['dictionary'] if 'dictionary' in message else None,
                    'class': message['class'] if 'class' in message else None,
                    'instance_id': message['instance_id'] if 'instance_id' in message else None
                })                    
            )

            if 'instance_id' in message and message['instance_id'] is not None:
                instance, _ = model.instances.get_or_create(
                    stepfile_id = message['instance_id'],
                    model=model
                )
                outcome.instance = instance
                outcome.save()
        
        # update Model info
        agg_status = context.task.determine_aggregate_status()
        model.status_bsdd = agg_status
        model.save(update_fields=['status_bsdd'])

        return f"agg_status = {Model.Status(agg_status).label}\nmessages = {json_output['messages']}"