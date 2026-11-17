"""Persist representative validation reports for backend and browser tests."""
from apps.ifc_validation_models.models import Model, ModelInstance, ValidationOutcome, ValidationRequest, ValidationTask


def create_case(case, user):
    model = Model.objects.create(file_name=case["file_name"], file=case["file_name"], size=case["size"],
                                 uploaded_by=user, **case["model"])
    request = ValidationRequest.objects.create(file_name=case["file_name"], file=case["file_name"], size=case["size"],
                                                model=model, status="COMPLETED", progress=100)
    instances = {spec["stepfile_id"]: ModelInstance.objects.create(model=model, **spec) for spec in case["instances"]}
    for task in case["tasks"]:
        validation_task = ValidationTask.objects.create(request=request, type=task["type"], status=task.get("status", "COMPLETED"),
                                                         progress=100, status_reason=task.get("status_reason", ""))
        for outcome in task.get("outcomes", []):
            ValidationOutcome.objects.create(
                validation_task=validation_task, instance=instances.get(outcome.get("instance")),
                severity_in_db=outcome["severity"], outcome_code=outcome.get("outcome_code", "E00020"),
                feature=outcome.get("feature"), feature_version=outcome.get("feature_version"),
                expected=outcome.get("expected"), observed=outcome.get("observed"),
            )
    return request
