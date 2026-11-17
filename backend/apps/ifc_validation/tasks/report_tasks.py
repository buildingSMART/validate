"""Post-validation exports. A rendering failure never changes validation results."""
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from apps.ifc_validation_models.decorators import requires_django_user_context

from .logger import logger


# acks_late=False: with the global acks_late + reject_on_worker_lost, a render whose worker
# is killed (e.g. out of memory) would be redelivered without end.
@shared_task(bind=True, max_retries=2, soft_time_limit=120, time_limit=150, acks_late=False)
@requires_django_user_context
def generate_validation_report(self, request_id):
    from apps.ifc_validation_bff.report.pdf import generate_pdf

    try:
        path = generate_pdf(request_id)
        return str(path) if path else None
    except SoftTimeLimitExceeded:
        # A report that does not render within the limit will not render on a retry either.
        logger.warning(f"PDF for validation request {request_id} exceeded the time limit; not retrying.")
        return None
    except Exception as error:
        raise self.retry(exc=error, countdown=30 * (self.request.retries + 1))
