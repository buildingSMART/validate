import datetime

from django.test import TestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *
from apps.ifc_validation_models.decorators import requires_django_user_context

from .tasks import schema_validation_subtask
from .tasks import syntax_validation_subtask
from .tasks import parse_info_subtask
from .tasks import prerequisites_subtask
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
    def test_parse_info_task_does_not_create_validation_outcome(self):

        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 0)

    @requires_django_user_context
    def test_parse_info_task_does_not_create_validation_outcome_2(self):

        request = ValidationRequest.objects.create(
            file_name='invalid_version.ifc',
            file='invalid_version.ifc', 
            size=281
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 0)

    @requires_django_user_context
    def test_parse_info_task_parses_properties(self):

        request = ValidationRequest.objects.create(
            file_name='wall-with-opening-and-window.ifc',
            file='wall-with-opening-and-window.ifc', 
            size=1
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEqual(model.mvd, 'CoordinationView')
        self.assertEqual(model.schema, 'IFC4')
        self.assertEqual(model.number_of_elements, 2)
        self.assertEqual(model.number_of_geometries, 4)
        self.assertEqual(model.number_of_properties, 19)

    @requires_django_user_context
    def test_parse_info_task_parses_date(self):

        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEqual(model.date, datetime.datetime(2022, 5, 4, 8, 8, 30, tzinfo=datetime.timezone.utc))

    @requires_django_user_context
    def test_parse_info_task_parses_date_with_timezone(self):

        request = ValidationRequest.objects.create(
            file_name='valid_file_with_tz.ifc',
            file='valid_file_with_tz.ifc', 
            size=1
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEqual(model.date, datetime.datetime(2023, 12, 16, 16, 20, 00, tzinfo=datetime.timezone.utc))

    @requires_django_user_context
    def test_parse_info_task_parses_authoring_tool(self):

        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEquals('IfcOpenShell-0.7.0', model.produced_by.name)
        self.assertEquals('0.7.0', model.produced_by.version)

    @requires_django_user_context
    def test_parse_info_task_parses_no_authoring_tool(self):

        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.mark_as_initiated()

        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertIsNone(model.produced_by)

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

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.PASSED)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.PASSED)
        self.assertEqual(outcomes.first().observed, None)

    @requires_django_user_context
    def test_schema_validation_task_creates_passed_validation_outcome_2(self):

        request = ValidationRequest.objects.create(
            file_name='wall-with-opening-and-window.ifc',
            file='wall-with-opening-and-window.ifc', 
            size=12789
        )
        request.mark_as_initiated()

        schema_validation_subtask(
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

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 3)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        self.assertTrue('(exists(lastmodifieddate) or' in outcomes.first().observed)
        self.assertTrue('Violated by:' in outcomes.first().observed)

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

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        self.assertEqual(outcomes.first().observed, 'Unsupported schema: ifc99')

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcome_2(self):

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

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes.first().severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes.first().outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        self.assertEqual(outcomes.first().observed, "(hiindex(self.Decomposes) == 1 and 'ifc4.ifcrelaggregates' in typeof(self.Decomposes[1]) and ('ifc4.ifcproject' in typeof(self.Decomposes[1].RelatingObject) or 'ifc4.ifcspatialstructureelement' in typeof(self.Decomposes[1].RelatingObject)))\n\nViolated by:\n    ((0 == 1))\n     +  where 0 = hiindex(())\n     +    where () = #21=IfcSite('34KU2ViPP1tfFN7f9HiBe8',#5,$,$,$,$,$,$,$,$,$,$,$,$).Decomposes\n\nOn instance:\n    #21=IfcSite('34KU2ViPP1tfFN7f9HiBe8',#5,$,$,$,$,$,$,$,$,$,$,$,$)\n")
        self.assertEqual(outcomes.first().feature, '{"type": "entity_rule", "attribute": "IfcSpatialStructureElement.WR41"}')
        self.assertIsNotNone(outcomes.first().instance)
        self.assertEqual(outcomes.first().instance.stepfile_id, 21)
        self.assertEqual(outcomes.first().instance.ifc_type, 'IfcSite')

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes(self):

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

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 3)
        self.assertEqual(outcomes[0].severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes[1].severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes[2].severity, ValidationOutcome.OutcomeSeverity.ERROR)
        self.assertEqual(outcomes[0].outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        self.assertEqual(outcomes[1].outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        self.assertEqual(outcomes[2].outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)

    @requires_django_user_context
    def test_schema_validation_task_creates_error_validation_outcomes_2(self):

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

        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 12)
        for idx in range(0,11):
            self.assertEqual(outcomes[idx].severity, ValidationOutcome.OutcomeSeverity.ERROR)
            self.assertEqual(outcomes[idx].outcome_code, ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR)
        
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
            