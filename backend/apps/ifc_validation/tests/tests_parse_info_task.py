import datetime

from django.test import TestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *
from apps.ifc_validation_models.decorators import requires_django_user_context

from ..tasks import parse_info_subtask

class ParseInfoTasksTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):

        """
        Creates a SYSTEM user in the (in-memory) test database.
        Runs once for the whole test case.
        """

        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        user.save()

    @requires_django_user_context
    def test_parse_info_task_valid_file_does_not_create_validation_outcome(self):

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
    def test_parse_info_task_invalid_version_does_not_create_validation_outcome(self):

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
    def test_parse_info_task_correctly_parses_properties(self):

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
    def test_parse_info_task_correctly_parses_date(self):

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
    def test_parse_info_task_correctly_parses_date_with_timezone(self):

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
    def test_parse_info_task_correctly_parses_authoring_tool(self):

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
    def test_parse_info_task_correctly_parses_missing_authoring_tool(self):

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
        