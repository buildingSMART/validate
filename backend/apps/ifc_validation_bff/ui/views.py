from dataclasses import replace
from functools import wraps
from urllib.parse import urlencode

from django.contrib.auth import logout as auth_logout
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.vary import vary_on_headers
from django.views.decorators.csrf import csrf_protect

from ..views_legacy import get_current_user
from .actions import delete_files, upload_files
from .content import landing_page
from ..datamodel.ui import UploadForm
from ..datamodel.load import dashboard_options, load_allowlist, load_dashboard, load_shell, upload_policy


def redirect_to(request, url):
    return HttpResponse(headers={"HX-Redirect": url}) if request.headers.get("HX-Request") == "true" else HttpResponseRedirect(url)


def authenticated(view):
    @wraps(view)
    def inner(request, *args, **kwargs):
        user = get_current_user(request)
        if user is None:
            return redirect_to(request, "/v2/login?" + urlencode({"next": request.get_full_path()}))
        if not user.is_active:
            return redirect_to(request, "/v2/waiting_zone")
        return view(request, *args, user=user, **kwargs)
    return inner


def page(request, template, title, active, user=None, status=200, **context):
    return render(request, template, {"shell": load_shell(request, user, title, active), **context}, status=status)


@require_GET
def home(request):
    user = get_current_user(request)
    policy = upload_policy()
    return page(request, "ui/home.html", "IFC Validation Service", "home", user if user and user.is_active else None,
                landing=landing_page(policy.max_size_mb), upload=UploadForm(policy))


@require_GET
@authenticated
@vary_on_headers("HX-Request")
def dashboard(request, user):
    template = "ui/dashboard_panel.html" if request.headers.get("HX-Request") == "true" else "ui/dashboard.html"
    return page(request, template, "Validation", "dashboard", user,
                dashboard=load_dashboard(user, dashboard_options(request.GET)), upload=UploadForm(upload_policy()))


@require_GET
@authenticated
def allowlist(request, user):
    return page(request, "ui/allowlist.html", "Allowlist", "allowlist", user, allowlist=load_allowlist())


@require_GET
def scorecards(request):
    user = get_current_user(request)
    return page(request, "ui/scorecards.html", "Scorecards Service", "scorecards", user if user and user.is_active else None)


@require_GET
def waiting_zone(request):
    return page(request, "ui/waiting_zone.html", "Awaiting User Activation", "waiting_zone")


@require_POST
@csrf_protect
@authenticated
def upload(request, user):
    policy = upload_policy()
    errors = upload_files(request.FILES.getlist("file"), policy)
    if errors:
        template = "ui/upload.html" if request.headers.get("HX-Request") == "true" else "ui/upload_page.html"
        return page(request, template, "Upload IFC files", "dashboard", user, status=422, upload=UploadForm(policy, errors))
    return redirect_to(request, "/v2/dashboard")


@require_POST
@csrf_protect
@authenticated
def delete(request, user, id=None):
    errors = delete_files(user, (id,) if id else request.POST.getlist("selected"))
    if request.headers.get("HX-Request") != "true":
        return redirect_to(request, "/v2/dashboard") if not errors else page(
            request, "ui/dashboard.html", "Validation", "dashboard", user, status=422,
            dashboard=replace(load_dashboard(user, dashboard_options(request.POST)), errors=errors),
            upload=UploadForm(upload_policy()))
    data = load_dashboard(user, dashboard_options(request.POST))
    return page(request, "ui/dashboard_panel.html", "Validation", "dashboard", user,
                dashboard=replace(data, errors=errors))


@require_POST
@csrf_protect
@authenticated
def affiliation(request, user):
    answer = request.POST.get("is_vendor_self_declared")
    if answer not in ("true", "false"):
        return HttpResponse("Choose whether you are affiliated with a software company.", status=422)
    info = user.useradditionalinfo
    info.is_vendor_self_declared = answer == "true"
    info.save(update_fields=["is_vendor_self_declared"])
    if request.headers.get("HX-Request") == "true":
        return HttpResponse('<div id="affiliation-dialog"></div>')
    return redirect_to(request, "/v2/dashboard")


@require_GET
def login(request):
    # Keep the registered OAuth callback URI; the callback returns to this UI.
    target = request.GET.get("next", "/v2/dashboard")
    request.session["ui_return_to"] = target if target.startswith("/v2/") and "\\" not in target else "/v2/dashboard"
    from core.views_auth import login as oauth_login
    return oauth_login(request)


@require_GET
def callback(request):
    # The normal provider callback is still /callback; this preserves the UI route too.
    from core.views_auth import callback as oauth_callback
    request.session.setdefault("ui_return_to", "/v2/dashboard")
    return oauth_callback(request)


@require_http_methods(["GET", "POST"])
@csrf_protect
def logout(request):
    if request.method == "POST":
        auth_logout(request)
        return redirect_to(request, "/v2/")
    return page(request, "ui/logout.html", "Logout", "logout", get_current_user(request))


def not_found(request, path=None):
    return page(request, "ui/not_found.html", "Not Found", "", get_current_user(request), status=404)
