from django.test import TestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *
from apps.ifc_validation_models.decorators import requires_django_user_context

from .tasks import syntax_validation_subtask
from .tasks import bsdd_validation_subtask

class ValidationTasksTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):

        """
        Creates a SYSTEM user in the (in-memory) test database.
        Runs once for the whole test case.
        """

        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        user.save()

    @requires_django_user_context
    def test_syntax_validation_task_creates_passed_validation_outcome(self):

        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
        self.assertEqual(outcomes.first().observed, None)

    @requires_django_user_context
    def test_syntax_validation_task_creates_error_validation_outcome(self):

        request = ValidationRequest.objects.create(
            file_name='invalid_file.ifc',
            file='invalid_file.ifc', 
            size=7
        )
        request.mark_as_initiated()

        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        self.assertTrue('On line 1 column 1' in outcomes.first().observed)

    @requires_django_user_context
    def test_determine_aggregate_status_for_multiple_outcomes(self):

        # test cases
        TEST_CASES = [
            {
                'input': [
                    ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE, 
                    ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE, 
                    ValidationOutcome.OutcomeSeverity.EXECUTED
                ], 
                'output': Model.Status.VALID
            },
            {
                'input': [
                    ValidationOutcome.OutcomeSeverity.EXECUTED, 
                    ValidationOutcome.OutcomeSeverity.PASSED, 
                    ValidationOutcome.OutcomeSeverity.EXECUTED
                ], 
                'output': Model.Status.VALID
            },
            {
                'input': [
                    ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE, 
                    ValidationOutcome.OutcomeSeverity.WARNING,
                    ValidationOutcome.OutcomeSeverity.PASSED, 
                    ValidationOutcome.OutcomeSeverity.EXECUTED
                ], 
                'output': Model.Status.WARNING
            },
            {
                'input': [
                    ValidationOutcome.OutcomeSeverity.WARNING, 
                    ValidationOutcome.OutcomeSeverity.PASSED, 
                    ValidationOutcome.OutcomeSeverity.ERROR
                ], 
                'output': Model.Status.INVALID
            },
            {
                'input': [], 
                'output': Model.Status.VALID
            }
        ]

        # arrange
        request = ValidationRequest.objects.create(
            file_name='abc.ifc',
            file='abc.ifc', 
            size=0
        )
        request.mark_as_initiated()

        for test_case in TEST_CASES:

            task = ValidationTask.objects.create(request=request)

            for severity in test_case['input']:
                ValidationOutcome.objects.create(validation_task=task, severity=severity)

            # act
            final_status = task.determine_aggregate_status()

            # assert
            self.assertEqual(final_status, test_case['output'])

    @requires_django_user_context
    def test_bsdd_validation_task_creates_na_validation_outcome(self):

        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        bsdd_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].severity, ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE)

    @requires_django_user_context
    def test_bsdd_validation_task_creates_na_validation_outcome_2(self):

        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1
        )
        request.mark_as_initiated()

        bsdd_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].severity, ValidationOutcome.OutcomeSeverity.NOT_APPLICABLE)
            