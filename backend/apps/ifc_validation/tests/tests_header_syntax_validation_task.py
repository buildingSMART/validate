from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import header_syntax_validation_subtask

class SyntaxValidationTaskTestCase(TransactionTestCase):

    def set_user_context():
        user, _ = User.objects.get_or_create(id=1, defaults={'username': 'SYSTEM', 'is_active': True})
        set_user_context(user)

    def test_header_syntax_validation_task_creates_passed_validation_outcome(self):

        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        header_syntax_validation_subtask(
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

    def test_header_syntax_validation_task_creates_error_validation_outcome(self):

        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_invalid_header_entity.ifc',
            file='fail_invalid_header_entity.ifc', 
            size=7
        )
        request.mark_as_initiated()

        header_syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        self.assertTrue('On line 5 column 1' in outcomes.first().observed, outcomes.first().observed)

    def test_header_syntax_validation_task_reports_correct_line_for_raw_utf8(self):

        # the only_header parser reconstructs the header before parsing and used to
        # report line 3 (FILE_DESCRIPTION) for a non-ASCII character on line 4 (FILE_NAME)
        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_non_ascii_raw_utf8_header.ifc',
            file='fail_non_ascii_raw_utf8_header.ifc',
            size=os.path.getsize('apps/ifc_validation/fixtures/fail_non_ascii_raw_utf8_header.ifc'),
        )
        request.mark_as_initiated()

        header_syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'},
            id=request.id,
            file_name=request.file_name,
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR)
        observed = outcomes.first().observed
        self.assertIn("Unexpected character ('0xed')", observed)
        self.assertIn('On line 4 column', observed)
        self.assertNotIn('UnicodeDecodeError', observed)

    def test_header_syntax_validation_task_translates_unicode_decode_error(self):

        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_non_ascii_latin1_header.ifc',
            file='fail_non_ascii_latin1_header.ifc',
            size=os.path.getsize('apps/ifc_validation/fixtures/fail_non_ascii_latin1_header.ifc'),
        )
        request.mark_as_initiated()

        header_syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'},
            id=request.id,
            file_name=request.file_name,
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        observed = outcomes.first().observed
        self.assertNotIn('UnicodeDecodeError', observed)
        self.assertNotIn('Traceback', observed)
        self.assertIn('On line 4 column', observed)
        self.assertIn('\\X2\\', observed)

    def test_header_syntax_validation_task_passes_x2_escaped_header(self):

        # correctly escaped non-ASCII characters (\X2\00ED\X0\) are valid STEP and must pass
        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='pass_non_ascii_x2_escape_header.ifc',
            file='pass_non_ascii_x2_escape_header.ifc',
            size=os.path.getsize('apps/ifc_validation/fixtures/pass_non_ascii_x2_escape_header.ifc'),
        )
        request.mark_as_initiated()

        header_syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'},
            id=request.id,
            file_name=request.file_name,
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)

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
    
    def test_syntax_error_in_data_section_does_not_create_header_syntax_validation_error(self):
        SyntaxValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='fail_double_comma.ifc',
            file='fail_double_comma.ifc', 
            size=7
        )
        request.mark_as_initiated()

        header_syntax_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes, outcomes)
        self.assertEqual(len(outcomes), 1, outcomes)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
