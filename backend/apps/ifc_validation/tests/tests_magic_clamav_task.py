import datetime

from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *
from apps.ifc_validation.tasks.utils import get_absolute_file_path

from ..tasks import magic_clamav_subtask

class MagicClamAVTaskTestCase(TransactionTestCase):

    def set_user_context():
        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        set_user_context(user)

    def test_magic_clamav_task_detects_valid_ifc_file(self):

        # arrange
        MagicClamAVTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.mark_as_initiated()

        # act
        task = magic_clamav_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )
        print(task)

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEqual(model.status_magic_clamav, Model.Status.VALID)

    def test_magic_clamav_task_detects_eicar_testfile(self):

        # arrange
        MagicClamAVTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='eicar_testfile.ifc',
            file='eicar_testfile.ifc', 
            size=68
        )
        request.mark_as_initiated()

        # make sure the test file contains eicar test string
        file_path = get_absolute_file_path(request.file.name)
        with open(file_path, 'w') as f:
            EICAR_TEST_STRING = 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
            f.write(EICAR_TEST_STRING)

        # act
        task = magic_clamav_subtask(
            prev_result={'is_valid': True, 'reason': 'test'}, 
            id=request.id, 
            file_name=request.file_name
        )
        print(task)

        # assert
        model = Model.objects.get(id=request.id)
        self.assertIsNotNone(model)
        self.assertEqual(model.status_magic_clamav, Model.Status.INVALID)
        