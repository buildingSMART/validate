from contextlib import contextmanager
from unittest import mock

from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import (
    ValidationRequest,
    ValidationTask,
    set_user_context,
)

from ..tasks.configs import task_registry
from ..tasks import schema_validation_subtask
import apps.ifc_validation.tasks.task_runner as task_runner


@contextmanager
def _noop_lock(*args, **kwargs):
    # Replaces the redis-backed user task lock so these tests stay hermetic.
    yield None


@mock.patch.object(task_runner, "acquire_user_lock", _noop_lock)
class ProgressUpdateTaskTestCase(TransactionTestCase):
    """Progress must advance only after a subtask's work finishes, so a request
    never reports 100% while a task is still running."""

    TASK_TYPE = ValidationTask.Type.SCHEMA  # increment = 10

    def setUp(self):
        user, _ = User.objects.get_or_create(
            id=1, defaults={"username": "SYSTEM", "is_active": True}
        )
        set_user_context(user)
        self.config = task_registry[self.TASK_TYPE]
        self.increment = self.config.increment

    def _make_request(self, progress=0):
        request = ValidationRequest.objects.create(
            file_name="valid_file.ifc", file="valid_file.ifc", size=280
        )
        request.mark_as_initiated()  # progress -> 0
        if progress:
            ValidationRequest.objects.filter(pk=request.id).update(progress=progress)
        return request

    def _run(self, request):
        schema_validation_subtask(
            prev_result={"is_valid": True, "reason": "test"},
            id=request.id,
            file_name=request.file_name,
        )

    def test_progress_advances_only_after_task_work_completes(self):
        request = self._make_request()
        seen = {}

        def fake_check(context):
            seen["during_check"] = ValidationRequest.objects.get(pk=request.id).progress
            return context

        def fake_process(context):
            seen["during_process"] = ValidationRequest.objects.get(pk=request.id).progress
            return "ok"

        with mock.patch.object(self.config, "check_program", side_effect=fake_check), \
             mock.patch.object(self.config, "process_results", side_effect=fake_process):
            self._run(request)

        # During the task body, progress must not have advanced (the bug: it was
        # bumped before the work ran).
        self.assertEqual(seen["during_check"], 0)
        self.assertEqual(seen["during_process"], 0)

        # It advances by the increment only after the task finishes.
        request.refresh_from_db()
        self.assertEqual(request.progress, self.increment)

    def test_progress_is_clamped_to_100(self):
        request = self._make_request(progress=95)  # 95 + 10 would overflow to 105

        with mock.patch.object(self.config, "check_program", return_value=None), \
             mock.patch.object(self.config, "process_results", return_value="ok"):
            self._run(request)

        request.refresh_from_db()
        self.assertEqual(request.progress, 100)

    def test_failed_task_does_not_advance_progress(self):
        request = self._make_request()

        with mock.patch.object(self.config, "check_program", side_effect=RuntimeError("boom")):
            self._run(request)

        request.refresh_from_db()
        self.assertEqual(request.progress, 0)

        task = ValidationTask.objects.filter(
            request_id=request.id, type=self.TASK_TYPE
        ).first()
        self.assertEqual(task.status, ValidationTask.Status.FAILED)
