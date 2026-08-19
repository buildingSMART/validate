from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import syntax_validation_subtask

class SyntaxValidationTaskTestCase(TransactionTestCase):

    def set_user_context():
        user, _ = User.objects.get_or_create(id=1, defaults={'username': 'SYSTEM', 'is_active': True})
        set_user_context(user)

    def test_syntax_validation_task_creates_passed_validation_outcome(self):

        SyntaxValidationTaskTestCase.set_user_context()
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

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
        self.assertEqual(outcomes.first().observed, None)

    def test_syntax_validation_task_creates_error_validation_outcome(self):

        SyntaxValidationTaskTestCase.set_user_context()
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

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        self.assertTrue('On line 1 column 1' in outcomes.first().observed)
    
    
    def test_syntax_validation_task_creates_error_for_utf8_bom(self):
        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='invalid_utf8_with_bom.ifc',
            file='invalid_utf8_with_bom.ifc',
            size=os.path.getsize('apps/ifc_validation/fixtures/invalid_utf8_with_bom.ifc'),
        )
        request.mark_as_initiated()

        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'},
            id=request.id,
            file_name=request.file_name,
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        self.assertIn("On line 1 column 1", outcomes.first().observed)
        self.assertIn("character", outcomes.first().observed.lower())


    def test_syntax_validation_task_translates_unicode_decode_error(self):

        # latin-1 encoded í crashes the parser; the raw traceback must never reach the user
        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_non_ascii_latin1_header.ifc',
            file='fail_non_ascii_latin1_header.ifc',
            size=os.path.getsize('apps/ifc_validation/fixtures/fail_non_ascii_latin1_header.ifc'),
        )
        request.mark_as_initiated()

        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'},
            id=request.id,
            file_name=request.file_name,
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        observed = outcomes.first().observed
        self.assertNotIn('UnicodeDecodeError', observed)
        self.assertNotIn('Traceback', observed)
        self.assertIn('On line 4 column', observed)
        self.assertIn("non-ASCII byte ('0xed')", observed)
        self.assertIn('\\X2\\', observed)

    def test_syntax_validation_task_reports_correct_position_for_raw_utf8(self):

        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_non_ascii_raw_utf8_header.ifc',
            file='fail_non_ascii_raw_utf8_header.ifc',
            size=os.path.getsize('apps/ifc_validation/fixtures/fail_non_ascii_raw_utf8_header.ifc'),
        )
        request.mark_as_initiated()

        syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'},
            id=request.id,
            file_name=request.file_name,
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertEqual(len(outcomes), 1)
        observed = outcomes.first().observed
        self.assertIn("Unexpected character ('0xed')", observed)
        # the í is in FILE_NAME on line 4; the reported line must point there
        self.assertIn('On line 4 column', observed)
        self.assertNotIn('UnicodeDecodeError', observed)

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
                'output': Model.Status.NOT_VALIDATED
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
