import os

from celery import Celery, Task
from celery.worker.request import Request
from celery.exceptions import Ignore
from celery.utils.log import get_task_logger

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

logger = get_task_logger(__name__)


class BaseTaskRequest(Request):

    """
    Default base class for all Celery task execution requests.
    """

    def on_timeout(self, soft, timeout):

        super().on_timeout(soft, timeout)
        logger.warning(f"A {'soft' if soft else 'hard'} timeout was enforced for task {self.task.name}")

    def on_failure(self, exc_info, send_failed_event=True, return_ok=False):

        super().on_failure(
            exc_info,
            send_failed_event=send_failed_event,
            return_ok=return_ok
        )
        logger.error(f'Failure detected for task {self.task.name} - {exc_info=}')


class BaseTask(Task):

    """
    Default base class for all Celery tasks.
    """

    Request = BaseTaskRequest

    def before_start(self, task_id, args, kwargs):
        logger.debug("*** BEFORE START ***")

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        logger.debug("*** AFTER RETURN ***")

    def on_success(self, retval, task_id, args, kwargs):
        logger.debug("*** SUCCESS ***")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warn("*** RETRY ***")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("*** FAILURE ***")

    def update_task_status(self, state, reason, is_final=True):

        """
        Update bespoke state and send event(s).
        """
        self.update_state(state=state, meta={'reason': reason})
        self.send_event('task-' + state, reason=reason)

        if is_final:
            raise Ignore()  # prevent Celery from going to SUCCESS state


app = Celery("core", task_cls=BaseTask)
app.config_from_object("django.conf:settings", namespace="CELERY")  # prefix 'CELERY_'
app.autodiscover_tasks()
