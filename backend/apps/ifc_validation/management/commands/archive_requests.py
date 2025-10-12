import os
import gzip
import shutil
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation.tasks.utils import get_absolute_file_path
from apps.ifc_validation_models.decorators import requires_django_user_context
from core.utils import format_human_readable_file_size

class Command(BaseCommand):
    
    help = 'Archive ValidationRequest files matching certain pruning criteria (age, deletion status). Compresses *.ifc files to *.ifc.gz and updates database records accordingly.'

    def add_arguments(self, parser):

        # how many days to look back (default: 180)
        parser.add_argument(
            '--days', '-d',
            type=int,
            default=180,
            help='Number of days to look back for old Validation Requests (default: 180).'
        )

        # whether to restrict to deleted requests only (default) or include non-deleted as well
        deleted_group = parser.add_mutually_exclusive_group()
        deleted_group.add_argument(
            '--deleted-only', '--deleted',
            dest='deleted_only',
            action='store_true',
            help='Archive only deleted Validation Requests (default).'
        )
        deleted_group.add_argument(
            '--include-non-deleted', '--all',
            dest='deleted_only',
            action='store_false',
            help='Include non-deleted Validation Requests as well.'
        )
        parser.set_defaults(deleted_only=True)

        #  dry-run mode: perform a simulation, do not modify any files or database records
        # just logs intended actions and outcomes to stdout
        dry_group = parser.add_mutually_exclusive_group()
        dry_group.add_argument(
            '--dry-run', '--simulate', '--recon',
            dest='dry_run',
            action='store_true',
            help='Dry run (default): show what would be archived without changing files or database records.'
        )
        dry_group.add_argument(
            '--confirm', '--apply',
            dest='dry_run',
            action='store_false',
            help='Confirm archiving: apply file archving and database record changes.'
        )
        parser.set_defaults(dry_run=True)

    @requires_django_user_context
    def handle(self, *args, **options):
        days = options['days']
        deleted_only = options['deleted_only']
        dry_run = options['dry_run']

        cutoff_date = timezone.now() - timedelta(days=days)

        # query by age, deleted flag and file name ending with .ifc
        qs = ValidationRequest.objects.filter(created__lt=cutoff_date, file__iendswith='.ifc')
        
        if deleted_only:
            qs = qs.filter(deleted=True)

        total = qs.count()
        self.stdout.write(f"Found {total} Validation Request(s) older than {days} day(s){' (deleted only)' if deleted_only else ''}.")
        if dry_run:
            self.stdout.write(self.style.WARNING("NOTE: Running in DRY-RUN mode. No changes will be made. Use --confirm to apply changes."))

        archived = 0
        skipped = 0
        total_savings = 0  # in MB

        for request in qs.iterator():
            
            # validate presence of file
            try:
                file_path = get_absolute_file_path(request.file.name)
            except FileNotFoundError:
                self.stdout.write(f"WARNING: File not found for Validation Request with id={request.id} - skipping...")
                skipped += 1
                continue
            
            gz_filename = file_path + '.gz'
            gz_filename_only = request.file.name + '.gz'

            # only report what would happen
            if dry_run:
                self.stdout.write(f"[DRY-RUN] Would archive and update ValidationRequest with id={request.id} from {request.file.name} to {gz_filename_only}")
                archived += 1
                total_savings += os.path.getsize(file_path) * 0.8
                continue

            # create gzip archive
            total_savings += os.path.getsize(file_path)
            with open(file_path, 'rb') as f_in, gzip.open(gz_filename, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            total_savings -= os.path.getsize(gz_filename)

            # update database and remove original file
            try:
                with transaction.atomic():
                    request.file.name = gz_filename_only
                    request.save(update_fields=['file'])
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        # Raise to trigger transaction rollback
                        raise RuntimeError(f"Failed to remove original file: {e}")
            except Exception as e:
                # Ensure DB not updated and clean up the created gzip to keep state unchanged
                try:
                    os.remove(gz_filename)
                except Exception:
                    pass
                skipped += 1
                self.stdout.write(self.style.ERROR(f"Failed to archive Validation Request with id={request.id}: {e} - rolling back changes..."))
                continue
            
            archived += 1
            self.stdout.write(f"Archived and updated Validation Request with id={request.id}: {gz_filename_only}")

        # show summary
        total_savings = format_human_readable_file_size(total_savings)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY-RUN would have archived {archived}, skipped {skipped}, total considered {total}."))
            self.stdout.write(self.style.WARNING(f"DRY-RUN would free up approx. {total_savings} (compression ratio of 80%)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Archived {archived}, skipped {skipped}, total considered {total}."))
            self.stdout.write(self.style.SUCCESS(f"Freed up {total_savings}."))
