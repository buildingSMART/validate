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
            help='Number of days to look back for old requests (default: 180).'
        )

        # whether to restrict to deleted requests only (default) or include non-deleted as well
        deleted_group = parser.add_mutually_exclusive_group()
        deleted_group.add_argument(
            '--deleted-only', '--deleted',
            dest='deleted_only',
            action='store_true',
            help='Archive only deleted requests (default).'
        )
        deleted_group.add_argument(
            '--include-non-deleted', '--all',
            dest='deleted_only',
            action='store_false',
            help='Include non-deleted requests as well.'
        )
        parser.set_defaults(deleted_only=True)

        # dry-run mode: do not modify files or database, just log intended actions
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry run: show what would be archived without changing files or database.'
        )

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
        self.stdout.write(f"Found {total} ValidationRequest(s) older than {days} day(s){' (deleted only)' if deleted_only else ''}.")
        if dry_run:
            self.stdout.write(self.style.WARNING("NOTE: Running in DRY-RUN mode. No changes will be made."))

        archived = 0
        skipped = 0
        total_savings = 0  # in MB

        for request in qs.iterator():
            
            # validate presence of file
            try:
                file_path = get_absolute_file_path(request.file.name)
            except FileNotFoundError:
                self.stdout.write(f"WARNING: File not found for request {request.id} - skipping...")
                skipped += 1
                continue
            
            gz_filename = file_path + '.gz'

            # only report what would happen
            if dry_run:
                self.stdout.write(f"[DRY-RUN] Would archive and update request file name to {request.id}: {gz_filename}")
                archived += 1
                total_savings += os.path.getsize(file_path) * 0.8
                continue

            # create gzip archive
            total_savings += os.path.getsize(file_path)
            with open(file_path, 'rb') as f_in, gzip.open(gz_filename, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            total_savings -= os.path.getsize(gz_filename)

            # update database and remove original file
            with transaction.atomic():
                request.file.name = gz_filename
                request.save(update_fields=['file'])
                os.remove(file_path)
            
            archived += 1
            self.stdout.write(f"Archived and updated request {request.id}: {gz_filename}")

        # show summary
        total_savings = format_human_readable_file_size(total_savings)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY-RUN would have archived {archived}, skipped {skipped}, total considered {total}."))
            self.stdout.write(self.style.WARNING(f"DRY-RUN would free up approx. {total_savings} (compression ratio of 80%)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Archived {archived}, skipped {skipped}, total considered {total}."))
            self.stdout.write(self.style.WARNING(f"Freed up {total_savings}."))
