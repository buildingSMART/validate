from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import syntax_validation_subtask

class SyntaxValidationTasksTestCase(TransactionTestCase):

    def set_user_context():
        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        set_user_context(user)

    def test_syntax_validation_task_creates_passed_validation_outcome(self):

        # arrange
        SyntaxValidationTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        # act
        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
        self.assertEqual(outcomes.first().observed, None)

    def test_syntax_validation_task_creates_error_validation_outcome(self):

        # arrange
        SyntaxValidationTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='invalid_file.ifc',
            file='invalid_file.ifc', 
            size=7
        )
        request.mark_as_initiated()

        # act
        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        self.assertTrue('On line 1 column 1' in outcomes.first().observed)
