from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TransactionTestCase, override_settings
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

from ..tasks.file_retention_tasks import apply_file_retention, remove_validated_file


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

    def test_apply_file_retention_remove_retains_removed_field(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        request = ValidationRequest.objects.create(
            file_name='valid_file.ifc',
            file='valid_file.ifc', 
            size=1
        )
        orig_file_removed = timezone.now() - timezone.timedelta(days=50)
        request.created = timezone.now() - timezone.timedelta(days=250)
        request.file_removed = orig_file_removed
        request.file = None
        request.save()
        
        # act
        task = apply_file_retention(dry_run=False, action="remove")

        # assert
        request = ValidationRequest.objects.get(id=request.id)
        self.assertIsNotNone(request.file_removed)
        self.assertEquals(orig_file_removed, request.file_removed)

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

    def test_remove_validated_file_clears_file_field(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            file_name = 'remove_validated_file_test.ifc'
            file_path = Path(media_root) / file_name
            file_path.write_text('ISO-10303-21;')
            request = ValidationRequest.objects.create(
                file_name=file_name,
                file='remove_validated_file_test.ifc',
                size=file_path.stat().st_size
            )

            # act
            result = remove_validated_file(id=request.id)

            # assert
            request = ValidationRequest.objects.get(id=request.id)
            self.assertEquals('', request.file)
            self.assertIsNotNone(request.file_removed)
            self.assertFalse(file_path.exists())
            self.assertIn(file_name, result)

    def test_remove_validated_file_is_idempotent(self):

        # arrange
        ApplyFileRetentionTaskTestCase.set_user_context()
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            request = ValidationRequest.objects.create(
                file_name='remove_validated_file_test.ifc',
                file='remove_validated_file_test.ifc',
                size=1
            )
            orig_file_removed = timezone.now() - timezone.timedelta(days=50)
            request.file = None
            request.file_removed = orig_file_removed
            request.save()

            # act
            result = remove_validated_file(id=request.id)

            # assert
            request = ValidationRequest.objects.get(id=request.id)
            self.assertEquals(orig_file_removed, request.file_removed)
            self.assertIn('already removed', result)
