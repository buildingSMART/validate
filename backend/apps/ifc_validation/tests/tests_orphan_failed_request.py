"""
IVS-750 "failing request without relating task" -- option B (the minimal/elegant fix).

This variant does NOT fabricate a synthetic task. Instead it fixes the two real
defects in on_workflow_failed:
  1. it could fire twice (error_handler via link_error AND chord_error_handler via
     chord on_error), double-sending the failure emails -> add an idempotency guard;
  2. it dumped raw celery args/kwargs into status_reason -> replace with a clean,
     human-readable reason (full detail stays in the logs).

Note: under option B the orphaned request still has NO ValidationTask
(request.tasks.count() == 0). That is intentional for B -- it explains the failure
on the request itself rather than inventing a task that never ran.
"""

from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import (
    set_user_context,
    ValidationRequest,
    ValidationTask,
)

from apps.ifc_validation.tasks.task_runner import (
    on_workflow_failed,
    on_workflow_completed,
)


class OrphanFailedRequestElegantTestCase(TestCase):

    @staticmethod
    def _set_user_context():
        user, _ = User.objects.get_or_create(
            id=1, defaults={'username': 'SYSTEM', 'is_active': True},
        )
        set_user_context(user)
        return user

    def _make_request(self):
        user = self._set_user_context()
        request = ValidationRequest.objects.create(
            file_name='orphan_file.ifc', file='orphan_file.ifc', size=123,
        )
        request.mark_as_initiated()
        if request.created_by_id is None:
            request.created_by = user
            request.save()
        return request

    # --- the failure is now FAILED with a clean reason, and no raw arg dump ---
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_admin_email_task')
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_email_task')
    def test_orphan_failure_sets_clean_reason(self, mock_user_email, mock_admin_email):
        request = self._make_request()

        result = on_workflow_failed.apply(args=[None, request.id], kwargs={})
        if result.failed():
            self.fail(f"on_workflow_failed raised: {result.traceback}")

        request.refresh_from_db()

        self.assertEqual(request.status, ValidationRequest.Status.FAILED)
        self.assertTrue(
            request.status_reason.startswith("Validation failed before any check could run"),
            f"reason should be human-readable, got: {request.status_reason!r}",
        )
        # No raw celery dump leaked into the user-visible reason.
        self.assertNotIn("args=", request.status_reason)
        self.assertNotIn("kwargs=", request.status_reason)
        # Option B intentionally does NOT create a synthetic task.
        self.assertEqual(request.tasks.count(), 0)
        mock_user_email.delay.assert_called_once()
        mock_admin_email.delay.assert_called_once()

    # --- firing twice no longer double-sends emails ---
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_admin_email_task')
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_email_task')
    def test_double_fire_is_idempotent(self, mock_user_email, mock_admin_email):
        request = self._make_request()

        first = on_workflow_failed.apply(args=[None, request.id], kwargs={})
        second = on_workflow_failed.apply(args=[None, request.id], kwargs={})
        for r in (first, second):
            if r.failed():
                self.fail(f"on_workflow_failed raised: {r.traceback}")

        request.refresh_from_db()
        self.assertEqual(request.status, ValidationRequest.Status.FAILED)
        self.assertEqual(mock_user_email.delay.call_count, 1,
                         "failure email must be sent exactly once across both firings")
        self.assertEqual(mock_admin_email.delay.call_count, 1,
                         "admin failure email must be sent exactly once across both firings")

    # --- when an exception is available it is surfaced in the reason ---
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_admin_email_task')
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_email_task')
    def test_reason_includes_exception_when_present(self, mock_user_email, mock_admin_email):
        request = self._make_request()

        # error callbacks may carry the original exception; id is still args[1].
        result = on_workflow_failed.apply(args=[ValueError("boom in syntax"), request.id], kwargs={})
        if result.failed():
            self.fail(f"on_workflow_failed raised: {result.traceback}")

        request.refresh_from_db()
        self.assertIn("boom in syntax", request.status_reason)

    # --- regression: the in-workflow failure path still has its relating task ---
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_admin_email_task')
    @patch('apps.ifc_validation.tasks.task_runner.send_failure_email_task')
    def test_completed_failure_path_has_relating_task(self, mock_user_email, mock_admin_email):
        request = self._make_request()
        ValidationTask.objects.create(
            request=request,
            type=ValidationTask.Type.SYNTAX,
            status=ValidationTask.Status.FAILED,
        )

        result = on_workflow_completed.apply(args=[None], kwargs={'id': request.id})
        if result.failed():
            self.fail(f"on_workflow_completed raised: {result.traceback}")

        request.refresh_from_db()
        self.assertEqual(request.status, ValidationRequest.Status.FAILED)
        self.assertEqual(request.tasks.count(), 1)
        mock_user_email.delay.assert_called_once()
        mock_admin_email.delay.assert_called_once()
