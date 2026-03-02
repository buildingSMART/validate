import os
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.decorators import requires_django_user_context

from apps.ifc_validation.tasks.utils import get_absolute_file_path
from core.utils import format_human_readable_file_size

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    
    help = 'Removes ValidationRequest files matching certain pruning criteria (age, deletion status). Removes *.ifc and *.ifc.gz and updates database records accordingly.'

    def add_arguments(self, parser):

        # how many days to look back (default: 180)
        parser.add_argument(
            '--days', '-d',
            type=int,
            default=180,
            help='Number of days to look back for old Validation Requests (default: 180).'
        )

        # whether to restrict to deleted requests only or include non-deleted as well (default)
        deleted_group = parser.add_mutually_exclusive_group()
        deleted_group.add_argument(
            '--deleted-only', '--deleted',
            dest='deleted_only',
            action='store_true',
            help='Archive only deleted Validation Requests.'
        )
        deleted_group.add_argument(
            '--include-non-deleted', '--all',
            dest='deleted_only',
            action='store_false',
            help='Include non-deleted Validation Requests as well (default).'
        )
        parser.set_defaults(deleted_only=False)

        # dry-run mode: perform a simulation, do not modify any files or database records
        # just logs intended actions and outcomes to stdout
        dry_group = parser.add_mutually_exclusive_group()
        dry_group.add_argument(
            '--dry-run', '--simulate', '--recon',
            dest='dry_run',
            action='store_true',
            help='Dry run (default): show what would be removed without changing files or database records.'
        )
        dry_group.add_argument(
            '--confirm', '--apply',
            dest='dry_run',
            action='store_false',
            help='Confirm removal: apply file removal and database record changes.'
        )
        parser.set_defaults(dry_run=True)

    @requires_django_user_context
    def handle(self, *args, **options):
        days = options['days']
        deleted_only = options['deleted_only']
        dry_run = options['dry_run']

        cutoff_date = timezone.now() - timedelta(days=days)

        # query by age and deleted flag, and empty file names
        qs = ValidationRequest.objects.filter(created__lt=cutoff_date, file__isnull=False).exclude(file__exact='')
        if deleted_only:
            qs = qs.filter(deleted=True)

        total = qs.count()
        logger.info(f"Found {total} Validation Request(s) older than {days} day(s){' (deleted only)' if deleted_only else ''}.")
        if dry_run:
            logger.warning("NOTE: Running in DRY-RUN mode. No changes will be made. Use --confirm to apply changes.")

        removed = 0
        skipped = 0
        total_savings = 0  # in MB

        for request in qs.iterator():

            # validate presence of file
            file_name = request.file.name
            try:
                file_path = get_absolute_file_path(file_name)
                os.path.getsize(file_path)
            except FileNotFoundError:
                logger.warning(f"WARNING: File not found for Validation Request with id={request.id} ({request.file.name}) - skipping...")
                skipped += 1
                continue
            
            # only report what would happen
            if dry_run:
                logger.info(f"[DRY-RUN] Would update ValidationRequest with id={request.id} and remove file {file_name}")
                removed += 1
                total_savings += os.path.getsize(file_path)
                continue

            # calculate potential savings
            total_savings += os.path.getsize(file_path)

            # update database and remove original file
            try:
                with transaction.atomic():
                    request.remove_file()
                    try:
                        os.remove(file_path)
                    except OSError as e:
                        # Raise to trigger transaction rollback
                        raise RuntimeError(f"Failed to remove original file: {e}")
            except Exception as e:
                skipped += 1
                logger.error(f"Failed to remove Validation Request with id={request.id}: {e} - rolling back changes...")
                continue
            
            removed += 1
            logger.info(f"Removed file and updated Validation Request with id={request.id}: {file_name}")

        # show summary
        total_savings = format_human_readable_file_size(total_savings)
        if dry_run:
            logger.info(f"Actual run would have removed {removed}, skipped {skipped}, total considered {total}. Would free up approx. {total_savings}.")
        else:
            logger.info(f"Removed {removed}, skipped {skipped}, total considered {total}. Freed up {total_savings}.")
