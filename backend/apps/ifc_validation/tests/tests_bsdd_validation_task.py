from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import bsdd_validation_subtask

class BsddValidationTaskTestCase(TransactionTestCase):

    def set_user_context():
        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        set_user_context(user)

    def test_bsdd_validation_task_creates_na_validation_outcome(self):

        # arrange
        BsddValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        # act
        bsdd_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].severity, ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE)

    def test_bsdd_validation_task_creates_na_validation_outcome_2(self):

        # arrange
        BsddValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        bsdd_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].severity, ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE)
            