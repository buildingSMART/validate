import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.ifc_validation_models.models import ValidationRequest
from ..datamodel.report import TaskSummary
from .full import build_full_report
from ..datamodel.load import load_model_summary, load_report

RENDER_VERSION = '1'


def artifact_path(request):
    # A new validation run has a new identity; an older PDF is never advertised.
    identity = f'{RENDER_VERSION}:{request.pk}:{request.started}:{request.completed}:{request.model_id}'
    digest = hashlib.sha256(identity.encode()).hexdigest()[:20]
    root = Path(getattr(settings, 'VALIDATION_REPORT_ROOT', Path(settings.MEDIA_ROOT) / '.reports'))
    return root / request.public_id / f'{digest}.pdf'


def remove_pdf(request):
    folder = artifact_path(request).parent
    if folder.exists():
        for path in folder.glob('*.pdf'):
            path.unlink(missing_ok=True)


def load_full_report(request):
    inputs = {kind: load_report(request, kind, include_successful_syntax=True)
              for kind in ('file', 'syntax', 'schema', 'normative', 'industry')}
    latest = {}
    for task in request.tasks.order_by('-id'):
        latest.setdefault(task.type, task)
    tasks = tuple(TaskSummary(task.get_type_display(), task.get_status_display(), task.status_reason)
                  for task in sorted(latest.values(), key=lambda task: task.id))
    summary = load_model_summary(request)
    return build_full_report(inputs, generated_at=timezone.now().strftime('%d %B %Y · %H:%M UTC'),
                             validation_state=request.get_status_display(),
                             tasks=tasks, signature_status=summary.signatures_status, security_status=summary.security_status)


def static_asset_uri(url):
    """Only template-owned static assets can be fetched, never links from IFC data."""
    parsed = urlsplit(url)
    static = urlsplit(settings.STATIC_URL)
    if parsed.scheme not in ('http', 'https') or parsed.netloc not in ('report.invalid', static.netloc) or not parsed.path.startswith(static.path):
        raise ValueError(f'PDF asset is not a local static resource: {url}')
    name = unquote(parsed.path.removeprefix(static.path))
    if '..' in Path(name).parts:
        raise ValueError('Invalid PDF asset path')
    path = finders.find(name)
    if not path:
        raise FileNotFoundError(name)
    return Path(path).resolve().as_uri()


def render_pdf(document):
    from weasyprint import HTML, URLFetcher

    class StaticAssets(URLFetcher):
        """Restrict PDF asset fetching to the report's local static files."""

        def fetch(self, url, headers=None):
            return super().fetch(static_asset_uri(url), headers)

    html = render_to_string('report/page.html', {'pdf': True, 'document': document, 'report': document.file})
    return HTML(string=html, base_url='https://report.invalid/',
                url_fetcher=StaticAssets(allowed_protocols={'file'}, fail_on_errors=True)).write_pdf(
        presentational_hints=True)


def generate_pdf(request_id, *, force=False):
    request = ValidationRequest.objects.select_related('model', 'created_by', 'model__produced_by').get(pk=request_id)
    if request.deleted or request.file_removed or not request.has_final_status:
        return None
    target = artifact_path(request)
    if target.is_file() and not force:
        return target
    payload = render_pdf(load_full_report(request))
    with transaction.atomic():
        current = ValidationRequest.objects.select_for_update().get(pk=request_id)
        if current.deleted or current.file_removed or not current.has_final_status or artifact_path(current) != target:
            return None  # deleted/revalidated while rendering
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(dir=target.parent, suffix='.tmp', delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
            os.replace(temporary, target)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
    return target
