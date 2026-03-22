from io import StringIO

from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks.file_retention_tasks import apply_file_retention
from ..tasks.utils import get_absolute_file_path


class ApplyFileRetentionTaskTestCase(TransactionTestCase):

    def set_user_context():
        user, _ = User.objects.get_or_create(id=1, defaults={'username': 'SYSTEM', 'is_active': True})
        set_user_context(user)

    def test_apply_file_retention_archive_updates_file_name(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.created = timezone.now() - timezone.timedelta(days=250)
        request.save()
        
        # act
        task = apply_file_retention(dry_run=False, action="archive")

        # assert
        request = ValidationRequest.objects.get(id=request.id)
        self.assertIsNotNone(request.file)
        self.assertEquals('valid_file.ifc.gz', request.file.name)
    
    def test_apply_file_retention_archive_in_dry_mode_leaves_record_intact(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.created = timezone.now() - timezone.timedelta(days=250)
        request.save()
        
        # act
        task = apply_file_retention(dry_run=True, action="archive")

        # assert
        request = ValidationRequest.objects.get(id=request.id)
        self.assertIsNone(request.file_removed)
        self.assertEquals('valid_file.ifc', request.file)

    def test_apply_file_retention_remove_sets_file_removed_field(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.created = timezone.now() - timezone.timedelta(days=250)
        request.save()
        
        # act
        task = apply_file_retention(dry_run=False, action="remove")

        # assert
        request = ValidationRequest.objects.get(id=request.id)
        self.assertIsNotNone(request.file_removed)

    def test_apply_file_retention_remove_empties_file_field(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.created = timezone.now() - timezone.timedelta(days=250)
        request.save()
        
        # act
        task = apply_file_retention(dry_run=False, action="remove")

        # assert
        request = ValidationRequest.objects.get(id=request.id)
        self.assertEquals('', request.file)

    def test_apply_file_retention_remove_in_dry_mode_leaves_record_intact(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        request.created = timezone.now() - timezone.timedelta(days=250)
        request.save()
        
        # act
        task = apply_file_retention(dry_run=True, action="remove")

        # assert
        request = ValidationRequest.objects.get(id=request.id)
        self.assertIsNone(request.file_removed)
        self.assertNotEquals('', request.file)
