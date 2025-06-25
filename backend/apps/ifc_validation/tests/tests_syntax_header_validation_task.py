from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import syntax_header_validation_subtask

class SyntaxValidationTaskTestCase(TransactionTestCase):

    def set_user_context():
        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        set_user_context(user)

    def test_syntax_header_validation_task_creates_passed_validation_outcome(self):

        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        syntax_header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
        self.assertEqual(outcomes.first().observed, None)

    def test_syntax_header_validation_task_creates_error_validation_outcome(self):

        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_invalid_header_entity.ifc',
            file='fail_invalid_header_entity.ifc', 
            size=7
        )
        request.mark_as_initiated()

        syntax_header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_HEADER_ERROR)
        self.assertTrue('On line 5 column 1' in outcomes.first().observed, outcomes.first().observed)

    def test_determine_aggregate_status_for_multiple_outcomes(self):

        # test cases
        SyntaxValidationTaskTestCase.set_user_context()
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
    
    def test_syntax_error_in_data_section_does_not_create_syntax_header_validation_error(self):
        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_double_comma.ifc',
            file='fail_double_comma.ifc', 
            size=7
        )
        request.mark_as_initiated()

        syntax_header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes, outcomes)
        self.assertEqual(len(outcomes), 1, outcomes)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
