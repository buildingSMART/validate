
import json

from core.settings import DJANGO_DB_BULK_CREATE_BATCH_SIZE

from apps.ifc_validation_models.models import Model, ValidationOutcome
from .. import TaskContext, logger, with_model


def process_digital_signatures(context:TaskContext):
    output, success, valid = (context.result.get(k) for k in ("output", "success", "valid"))
    
    with with_model(context.request.id) as model:
        agg_status = Model.Status.NOT_APPLICABLE if not output else Model.Status.VALID if valid else Model.Status.INVALID
        setattr(model, context.config.status_field.name, agg_status)

        def create_outcome(di):
            return ValidationOutcome(
                severity=ValidationOutcome.OutcomeSeverity.ERROR if di.get("signature") == "invalid" else ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.VALUE_ERROR if di.get("signature") == "invalid" else ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=di,
                feature=json.dumps({'digital_signature': 1}),
                validation_task = context.task
            )

        ValidationOutcome.objects.bulk_create(list(map(create_outcome, output)), batch_size=DJANGO_DB_BULK_CREATE_BATCH_SIZE)

        model.save(update_fields=['status_signatures'])
        logger.info('Digital signature check completed' if success else f"Script returned exit code {context.result.returncode} and {context.result.stderr}")
