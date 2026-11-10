from pathlib import Path
import shutil

from django.core.management.base import BaseCommand, CommandError

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_bff.report.pdf import generate_pdf


class Command(BaseCommand):
    help = 'Generate full report PDFs for explicitly selected validation request ids.'

    def add_arguments(self, parser):
        parser.add_argument('ids', nargs='+', help='Private numeric or public r... request ids')
        parser.add_argument('--force', action='store_true', help='Regenerate an existing PDF')
        parser.add_argument('--output-dir', type=Path, help='Also copy review PDFs into this directory')

    def handle(self, *args, **options):
        for value in options['ids']:
            try:
                pk = ValidationRequest.to_private_id(value) if value.startswith('r') else int(value)
                path = generate_pdf(pk, force=options['force'])
            except (ValueError, ValidationRequest.DoesNotExist) as error:
                raise CommandError(f'Unknown validation request: {value}') from error
            if not path:
                raise CommandError(f'Request {value} is deleted or validation is still running.')
            if output := options['output_dir']:
                output.mkdir(parents=True, exist_ok=True)
                item = ValidationRequest.objects.get(pk=pk)
                name = Path(item.file_name.replace('\\', '/')).name
                destination = output / f'{item.public_id}-{Path(name).stem}.pdf'
                shutil.copyfile(path, destination)
                self.stdout.write(str(destination.resolve()))
            self.stdout.write(self.style.SUCCESS(f'Request {value}: {path}'))
