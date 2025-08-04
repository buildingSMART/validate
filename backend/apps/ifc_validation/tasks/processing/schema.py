import json
from django.db import transaction 

from core.settings import DJANGO_DB_BULK_CREATE_BATCH_SIZE

from apps.ifc_validation_models.models import ModelInstance, Model, ValidationOutcome
from .. import TaskContext, logger, with_model


def process_schema(context:TaskContext):
    output, success, valid = (context.result.get(k) for k in ("output", "success", "valid"))

    with with_model(context.request.id) as model:

        if valid:
            model.status_schema = Model.Status.VALID
            context.task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=None
            )
        else:
            model.status_schema = Model.Status.INVALID
            outcomes_to_save = list()
            outcomes_instances_to_save = list()

            for line in output:
                message = json.loads(line)
                outcome = ValidationOutcome(
                    severity=ValidationOutcome.OutcomeSeverity.ERROR,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR,
                    observed=message['message'],
                    feature=json.dumps({
                        'type': message['type'] if 'type' in message else None,
                        'attribute': message['attribute'] if 'attribute' in message else None
                    }),
                    validation_task=context.task
                )
                outcomes_to_save.append(outcome)
                if 'instance' in message and message['instance'] is not None and 'id' in message['instance'] and 'type' in message['instance']:
                    instance = ModelInstance(
                            stepfile_id=message['instance']['id'],
                            ifc_type=message['instance']['type'],
                            model=model
                        )
                    outcome.instance_id = instance.stepfile_id # store for later reference (not persisted)
                    outcomes_instances_to_save.append(instance)

            ModelInstance.objects.bulk_create(outcomes_instances_to_save, batch_size=DJANGO_DB_BULK_CREATE_BATCH_SIZE, ignore_conflicts=True) #ignore existing
            model_instances = dict(ModelInstance.objects.filter(model_id=model.id).values_list('stepfile_id', 'id')) # retrieve all

            for outcome in outcomes_to_save:
                if outcome.instance_id:
                    instance_id = model_instances[outcome.instance_id]
                    if instance_id:
                        outcome.instance_id = instance_id

            ValidationOutcome.objects.bulk_create(outcomes_to_save, batch_size=DJANGO_DB_BULK_CREATE_BATCH_SIZE)

        model.save(update_fields=['status_schema'])

        return "No IFC schema errors." if success else f"'ifcopenshell.validate' returned exit code {context.proc.returncode} and {len(output):,} errors."
