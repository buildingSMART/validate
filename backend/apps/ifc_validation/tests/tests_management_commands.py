from io import StringIO

from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TransactionTestCase

from apps.ifc_validation_models.models import (
    Model,
    ValidationOutcome,
    ValidationRequest,
    ValidationTask,
    set_user_context,
)
from core.redis_lock import acquire_user_lock


class DisplayUserLocksManagementCommandTestCase(TransactionTestCase):

    def test_display_user_locks_no_active_locks(self):

        # arrange
        test_user = User.objects.create_user(username='testuser', password='testpass')

        # act
        with self.assertLogs(level='INFO') as cm:
            call_command('display_user_locks')

            # assert
            self.assertTrue(any("No active user locks found." in message for message in cm.output))

    def test_display_user_locks_active_user_lock(self):

        # arrange
        test_user = User.objects.create_user(username='testuser', password='testpass')
        with acquire_user_lock(user_id=test_user.id, task_name='test_task') as lock:
            
            # act
            with self.assertLogs(level='INFO') as cm:
                call_command('display_user_locks')

                # assert
                print(cm.output)  # for debugging if test fails
                self.assertTrue(any(f"User ID: {test_user.id}, Task: test_task" in message for message in cm.output))


class PurgeIncompleteRequestsManagementCommandTestCase(TransactionTestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='purge-user', password='testpass')
        set_user_context(self.user)

    def create_request(self, name, status):
        return ValidationRequest.objects.create(
            file_name=name,
            file=name,
            size=1,
            status=status,
        )

    def attach_model(self, request):
        model = Model.objects.create(
            file_name=request.file_name,
            file=request.file,
            size=1,
            uploaded_by=self.user,
        )
        request.model = model
        request.save()
        return model

    def test_dry_run_reports_without_deleting(self):
        pending = self.create_request('pending.ifc', ValidationRequest.Status.PENDING)

        stdout = StringIO()
        call_command('purge_incomplete_requests', stdout=stdout)

        assert ValidationRequest.objects.filter(pk=pending.pk).exists()
        assert 'requests : 1' in stdout.getvalue()
        assert 'Dry run only' in stdout.getvalue()

    def test_confirm_deletes_incomplete_requests_models_tasks_and_outcomes(self):
        completed = self.create_request('done.ifc', ValidationRequest.Status.COMPLETED)
        completed_model = self.attach_model(completed)
        pending = self.create_request('pending.ifc', ValidationRequest.Status.PENDING)
        pending_model = self.attach_model(pending)
        task = ValidationTask.objects.create(
            request=pending,
            type=ValidationTask.Type.SYNTAX,
        )
        outcome = ValidationOutcome.objects.create(validation_task=task)

        call_command('purge_incomplete_requests', '--confirm')

        assert not ValidationRequest.objects.filter(pk=pending.pk).exists()
        assert not Model.objects.filter(pk=pending_model.pk).exists()
        assert not ValidationTask.objects.filter(pk=task.pk).exists()
        assert not ValidationOutcome.objects.filter(pk=outcome.pk).exists()
        assert ValidationRequest.objects.filter(pk=completed.pk).exists()
        assert Model.objects.filter(pk=completed_model.pk).exists()

    def test_status_filter_limits_the_purge(self):
        pending = self.create_request('pending.ifc', ValidationRequest.Status.PENDING)
        failed = self.create_request('failed.ifc', ValidationRequest.Status.FAILED)

        call_command('purge_incomplete_requests', '--confirm', '--status', 'FAILED')

        assert ValidationRequest.objects.filter(pk=pending.pk).exists()
        assert not ValidationRequest.objects.filter(pk=failed.pk).exists()