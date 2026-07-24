from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TransactionTestCase

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