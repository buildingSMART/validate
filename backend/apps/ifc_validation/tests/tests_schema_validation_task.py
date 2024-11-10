from django.test import TestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *
from apps.ifc_validation_models.decorators import requires_django_user_context

from ..tasks import schema_validation_subtask

class SchemaValidationTasksTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):

        """
        Creates a SYSTEM user in the (in-memory) test database.
        Runs once for the whole test case.
        """

        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        user.save()

    @requires_django_user_context
    def test_schema_validation_task_creates_passed_validation_outcome(self):

        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        schema_validation_subtask(
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

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes(self):

        request = ValidationRequest.objects.create(
            file_name='fail-alb005-scenario01-STATION_without_position.ifc',
            file='fail-alb005-scenario01-STATION_without_position.ifc', 
            size=1682
        )
        request.mark_as_initiated()

        schema_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 4)
        for outcome in outcomes:
            self.assertEqual(outcome.severity, ValidationOutcome.OutcomeSeverity.ERROR)
            self.assertEqual(outcome.outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)        
            self.assertTrue('Violated by:' in outcome.observed)
            self.assertTrue('On instance:' in outcome.observed)

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcome(self):

        request = ValidationRequest.objects.create(
            file_name='invalid_version.ifc',
            file='invalid_version.ifc', 
            size=281
        )
        request.mark_as_initiated()

        schema_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        self.assertEqual(outcomes.first().observed, 'Unsupported schema: ifc99')

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes(self):

        request = ValidationRequest.objects.create(
            file_name='pass-ifc001-IFC4.ifc',
            file='pass-ifc001-IFC4.ifc', 
            size=1254
        )
        request.mark_as_initiated()

        schema_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 2)
        for outcome in outcomes:
            self.assertEqual(outcome.severity, ValidationOutcome.OutcomeSeverity.ERROR)
            self.assertEqual(outcome.outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
            self.assertIsNotNone(outcome.instance)

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes_2(self):

        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1166
        )
        request.mark_as_initiated()

        schema_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 6)
        for outcome in outcomes:
            self.assertEqual(outcome.severity, ValidationOutcome.OutcomeSeverity.ERROR)
            self.assertEqual(outcome.outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
            self.assertIsNotNone(outcome.instance)

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes_3(self):

        request = ValidationRequest.objects.create(
            file_name='fail-als015-scenario01-long_last_segment.ifc',
            file='fail-als015-scenario01-long_last_segment.ifc', 
            size=30485
        )
        request.mark_as_initiated()

        schema_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 7)
        for outcome in outcomes:
            self.assertEqual(outcome.severity, ValidationOutcome.OutcomeSeverity.ERROR)
            self.assertEqual(outcome.outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes_4(self):

        request = ValidationRequest.objects.create(
            file_name='fail-als015-scenario01-long_last_segment.ifc',
            file='fail-als015-scenario01-long_last_segment.ifc', 
            size=30485
        )
        request.mark_as_initiated()

        schema_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.filter(validation_task__request_id=request.id)
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 7)
        for outcome in outcomes:
            self.assertEqual(outcome.severity, ValidationOutcome.OutcomeSeverity.ERROR)
            self.assertEqual(outcome.outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)