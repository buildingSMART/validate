"""Post-validation exports. A rendering failure never changes validation results."""
from celery import shared_task

from apps.ifc_validation_models.decorators import requires_django_user_context


@shared_task(bind=True, max_retries=2, soft_time_limit=120, time_limit=150)
@requires_django_user_context
def generate_validation_report(self, request_id):
    from apps.ifc_validation_bff.report.pdf import generate_pdf

    try:
        path = generate_pdf(request_id)
        return str(path) if path else None
    except Exception as error:
        raise self.retry(exc=error, countdown=30 * (self.request.retries + 1))
