from django.http import FileResponse, HttpResponseNotAllowed, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.vary import vary_on_headers
from urllib.parse import urlencode

from apps.ifc_validation_models.models import ValidationRequest
from ..views_legacy import get_current_user, resolve_request_id
from .build import REPORT_TITLES, build_report
from ..datamodel.report import ReportOptions
from ..datamodel.load import load_report, load_shell


@vary_on_headers("HX-Request")
def report_html(request, id: str, kind=None):
    def missing(user=None):
        return render(request, 'ui/not_found.html', {'shell': load_shell(request, user, 'Not Found', 'report')}, status=404)

    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    kind = kind or request.GET.get("type") or "file"
    if kind not in REPORT_TITLES:
        return missing()
    user = get_current_user(request)
    if not user:
        from ..ui.views import redirect_to
        return redirect_to(request, '/v2/login?' + urlencode({'next': request.get_full_path()}))
    if not user.is_active:
        return HttpResponseRedirect('/v2/waiting_zone')
    private_id = resolve_request_id(id)
    if not private_id:
        return missing(user)
    requests = ValidationRequest.objects.select_related("model", "created_by", "model__produced_by")
    if not user.is_staff:
        requests = requests.filter(created_by=user, deleted=False)
    validation_request = requests.filter(id=private_id).first()
    if not validation_request:
        return missing(user)
    try:
        number = int(request.GET.get("page", "1"))
    except ValueError:
        number = 1
    options = ReportOptions(include_all=request.GET.get("include_all") == "1", page=number)
    data = load_report(validation_request, kind, viewer=user).outcomes_grouped()
    data, pagination = data.outcome_groups_paginated(kind, options)
    report = build_report(data, kind, include_all=options.include_all)
    page = pagination.with_report(report)
    template = "report/section.html" if request.headers.get("HX-Request") == "true" else "report/page.html"
    context = {"request": request, "report": page.report, "page": page}
    if template == "report/page.html":
        context["shell"] = load_shell(request, user, report.title, "report")
    return render(request, template, context)


def legacy_report_redirect(request, id):
    kind = request.GET.get('type') or 'file'
    if kind not in REPORT_TITLES:
        return HttpResponseNotFound()
    query = request.GET.copy()
    query.pop('type', None)
    segment = 'rules' if kind == 'normative' else kind
    url = reverse(f'ui:report-{segment}', kwargs={'id': id})
    return HttpResponseRedirect(url + ('?' + query.urlencode() if query else ''))


def report_pdf(request, id):
    from .pdf import artifact_path
    from ..ui.views import authenticated

    @authenticated
    def download(request, user):
        if request.method != 'GET':
            return HttpResponseNotAllowed(['GET'])
        pk = resolve_request_id(id)
        items = ValidationRequest.objects.filter(pk=pk, deleted=False)
        if not user.is_staff:
            items = items.filter(created_by=user)
        item = items.first()
        if not item or item.file_removed or not item.has_final_status:
            return HttpResponseNotFound('PDF report is not available.')
        path = artifact_path(item)
        try:
            handle = path.open('rb')
        except FileNotFoundError:
            return HttpResponseNotFound('PDF report has not been generated yet.')
        from pathlib import Path
        name = Path(item.file_name.replace('\\', '/')).stem
        response = FileResponse(handle, as_attachment=True, filename=f'{name}-validation-report.pdf', content_type='application/pdf')
        response['Cache-Control'] = 'private, no-store'
        return response

    return download(request)
