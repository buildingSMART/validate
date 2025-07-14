import datetime

from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks import header_validation_subtask

class HeaderValidationTaskTestCase(TransactionTestCase):

    def set_user_context():
        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        set_user_context(user)

    def test_header_validation_task_valid_file_does_not_create_validation_outcome(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=280
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 0)
    
    def test_header_validation_task_invalid_version_does_not_create_validation_outcome(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='invalid_version.ifc',
            file='invalid_version.ifc', 
            size=281
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        outcomes = ValidationOutcome.objects.all()
        self.assertIsNotNone(outcomes)
        self.assertEqual(len(outcomes), 0)

    def test_header_validation_task_correctly_parses_properties(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='wall-with-opening-and-window.ifc',
            file='wall-with-opening-and-window.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEqual(model.mvd, 'CoordinationView')
        self.assertEqual(model.schema, 'IFC4')

    def test_header_validation_task_correctly_parses_date(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='pass_reverse_comment.ifc',
            file='pass_reverse_comment.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEqual(model.date, datetime.datetime(2022, 5, 4, 8, 8, 30, tzinfo=datetime.timezone.utc))

    def test_header_validation_task_correctly_parses_date_with_timezone(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file_with_tz.ifc',
            file='valid_file_with_tz.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEqual(model.date, datetime.datetime(2025, 2, 13, 13, 58, 45, tzinfo=datetime.timezone.utc))

    def test_header_validation_task_correctly_parses_authoring_tool(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='pass_header_policy.ifc',
            file='pass_header_policy.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEquals('MyFabTool', model.produced_by.name)
        self.assertEquals('2025.1', model.produced_by.version)
        self.assertEquals('Acme Inc.', model.produced_by.company.name)

    def test_header_validation_task_correctly_parses_existing_authoring_tool(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        company, _ = Company.objects.get_or_create(name='Acme Inc.')
        request = ValidationRequest.objects.create(
            file_name='pass_header_policy.ifc',
            file='pass_header_policy.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEquals('MyFabTool', model.produced_by.name)
        self.assertEquals('2025.1', model.produced_by.version)
        self.assertEquals('Acme Inc.', model.produced_by.company.name)
        self.assertEquals(company.id, model.produced_by.id)

    def test_header_validation_task_correctly_parses_existing_authoring_tool2(self):

        # arrange
        HeaderValidationTaskTestCase.set_user_context()
        company, _ = Company.objects.get_or_create(name='ACME, Inc.') # NOTE: different company name, test file has 'Acme Inc.'!
        AuthoringTool.objects.get_or_create(name='MyFabTool', version='2025.1', company=company)
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        header_validation_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEquals('MyFabTool', model.produced_by.name)
        self.assertEquals('2025.1', model.produced_by.version)
        self.assertEquals('Acme Inc.', model.produced_by.company.name)
