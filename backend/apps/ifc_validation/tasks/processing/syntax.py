
import json

from apps.ifc_validation_models.models import Model, ValidationOutcome
from .. import TaskContext, logger, with_model


def process_syntax_outcomes(context:TaskContext):
    #todo - unify output for all task executions
    output, error_output, success = (context.result.get(k) for k in ("output", "error_output", "success"))

    # process
    with with_model(context.request.id) as model:
        status_field = context.config.status_field.name
        task = context.task
        if success:
            setattr(model, status_field, Model.Status.VALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=output if output else None
            )
        elif error_output:
            setattr(model, status_field, Model.Status.INVALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.ERROR,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                observed=list(filter(None, error_output.split("\n")))[-1]
            )
        else:
            for msg in json.loads(output):
                setattr(model, status_field, Model.Status.INVALID)
                task.outcomes.create(
                    severity=ValidationOutcome.OutcomeSeverity.ERROR,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                    observed=msg.get("message")
                )

        model.save(update_fields=[status_field])
        
        # return reason for logging
        logger.info("No IFC syntax error(s)." if success else f"Found IFC syntax errors:\n\nConsole: \n{output}\n\nError: {error_output}")


def process_syntax(context:TaskContext):
    return process_syntax_outcomes(context)

def process_header_syntax(context:TaskContext):
    return process_syntax_outcomes(context)