import os
import gzip
import shutil
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
    
    help = (
        'Archive or Remove Validation Request files matching certain pruning criteria (eg. age, deletion status).',
        'Either ompresses *.ifc files to *.ifc.gz (archive) or removes *.ifc/*.ifc.gz files (remove) and updates database records accordingly.'
    )

    def add_arguments(self, parser):
        
        # how many days to look back (default: 90)
        parser.add_argument(
            '--days', '-d',
            type=int,
            default=90,
            help='Number of days to look back for old Validation Requests (default: 90).'
        )

        # action to perform: archive or remove (default: archive)
        parser.add_argument(
            '--action',
            choices=['archive', 'remove'],
            default='archive',
            help='Action to perform on matching old files: "archive" (compress to .gz) or "remove" (delete completely). Default: archive'
        )

        # dry-run mode: perform a simulation, do not modify any files or database records
        # just logs intended actions and outcomes to stdout
        dry_group = parser.add_mutually_exclusive_group()
        dry_group.add_argument(
            '--dry-run', '--simulate', '--recon',
            dest='dry_run',
            action='store_true',
            help='Dry run: show what would happen without modifying files or database.'
        )
        dry_group.add_argument(
            '--confirm', '--apply',
            dest='dry_run',
            action='store_false',
            help='Apply the changes (archive/remove files and update DB).'
        )
        parser.set_defaults(dry_run=True)

    @requires_django_user_context
    def handle(self, *args, **options):
        days = options['days']
        action = options['action']
        archive = (action == 'archive')
        dry_run = options['dry_run']

        cutoff_date = timezone.now() - timedelta(days=days)

        qs = ValidationRequest.objects.filter(created__lt=cutoff_date)
        if archive:
            qs = qs.filter(file__iendswith='.ifc').exclude(file__exact='')
        else: 
            qs = qs.filter(file__isnull=False).exclude(file__exact='')

        total = qs.count()
        mode_str = "archiving" if archive else "removal"
        logger.info(f"Found {total} Validation Request(s) older than {days} day(s) eligible for {mode_str}.")

        if dry_run:
            logger.warning("NOTE: Running in DRY-RUN mode. No changes will be made. Use --confirm to apply.")

        processed = 0
        skipped = 0
        total_savings = 0  # bytes

        for request in qs.iterator():

            # validate presence of file
            try:
                file_path = get_absolute_file_path(request.file.name)
                original_size = os.path.getsize(file_path)
            except FileNotFoundError:
                file_path = None
                original_size = 0
                logger.warning(f"File not found for ValidationRequest id={request.id} ({request.file.name})")
                # skipped += 1
                # continue

            # original and target names
            original_name = request.file.name
            gz_filename = file_path + '.gz' if file_path else original_name + '.gz'
            gz_name_only = original_name + '.gz'

            # only report what would happen
            if dry_run:

                if archive:
                    msg = f"[DRY-RUN] Would archive {request.file.name} → {gz_name_only} (id={request.id})"
                    total_savings += original_size * 0.80  # rough estimate
                else:
                    msg = f"[DRY-RUN] Would remove {request.file.name} (id={request.id})"
                    total_savings += original_size

                processed += 1
                logger.info(msg)
                continue     
            
            # execute action
            if action == 'archive':

                if not file_path:
                    logger.warning(f"File not found for ValidationRequest id={request.id} ({request.file.name}) - skipping")
                    skipped += 1
                    continue

                try:
                    # create gzip archive
                    with open(file_path, 'rb') as f_in, gzip.open(gz_filename, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                    gz_size = os.path.getsize(gz_filename)
                    savings = original_size - gz_size

                    # update database and remove original file
                    with transaction.atomic():
                        request.file.name = gz_name_only
                        request.save(update_fields=['file'])
                        os.remove(file_path)

                    logger.info(f"Archived and updated Validation Request with id={request.id}: {gz_name_only}  (saved ~{format_human_readable_file_size(savings)})")
                    total_savings += savings
                    processed += 1

                except Exception as e:

                    # ensure DB not updated and clean up the created gzip to keep state unchanged
                    if os.path.exists(gz_filename):
                        try:
                            os.remove(gz_filename)
                        except Exception:
                            pass
                    logger.error(f"Failed to archive Validation Request with id={request.id}: {e}")
                    skipped += 1

            elif action == 'remove':

                try:
                    # update database and remove original file
                    with transaction.atomic():
                        original_name = request.file.name
                        request.file = None
                        request.file_removed = timezone.now()
                        request.save(update_fields=['file', 'file_removed'])
                        if file_path:
                            os.remove(file_path)

                    logger.info(f"Removed file and updated Validation Request with id={request.id}: {original_name}")
                    total_savings += original_size
                    processed += 1

                except Exception as e:
                    logger.error(f"Failed to remove file for id={request.id}: {e}")
                    skipped += 1

        # show summary
        savings_str = format_human_readable_file_size(total_savings)
        if dry_run:
            logger.info(
                f"Dry-run summary: would {action} {processed}, skip {skipped}, consider {total}. Estimated space saved: {savings_str}"
            )
        else:
            logger.info(
                f"Completed {mode_str} of {processed}, skipped {skipped}, total considered {total}. Freed up {savings_str}."
            )