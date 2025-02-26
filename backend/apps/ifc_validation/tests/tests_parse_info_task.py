import datetime

from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import parse_info_subtask

class ParseInfoTasksTestCase(TransactionTestCase):

    def set_user_context():
        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        set_user_context(user)

    def test_parse_info_task_valid_file_does_not_create_validation_outcome(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 0)

    def test_parse_info_task_invalid_version_does_not_create_validation_outcome(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='invalid_version.ifc',
            file='invalid_version.ifc', 
            size=281
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 0)

    def test_parse_info_task_correctly_parses_properties(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='wall-with-opening-and-window.ifc',
            file='wall-with-opening-and-window.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEqual(model.mvd, 'CoordinationView')
        self.assertEqual(model.schema, 'IFC4')

    def test_parse_info_task_correctly_parses_date(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEqual(model.date, datetime.datetime(2022, 5, 4, 8, 8, 30, tzinfo=datetime.timezone.utc))

    def test_parse_info_task_correctly_parses_date_with_timezone(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file_with_tz.ifc',
            file='valid_file_with_tz.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEqual(model.date, datetime.datetime(2023, 12, 16, 16, 20, 00, tzinfo=datetime.timezone.utc))

    def test_parse_info_task_correctly_parses_authoring_tool(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='pass_header_policy.ifc',
            file='pass_header_policy.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertEquals('MyFabTool', model.produced_by.name)
        self.assertEquals('2025.1', model.produced_by.version)
        #self.assertEquals('Acme Inc.', model.produced_by.company.name) - TODO

    def test_parse_info_task_correctly_parses_missing_authoring_tool(self):

        # arrange
        ParseInfoTasksTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        parse_info_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.all().first()
        self.assertIsNotNone(model)
        self.assertIsNone(model.produced_by)
        