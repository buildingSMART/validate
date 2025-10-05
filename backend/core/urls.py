import re
from django.contrib import admin
from django.http import HttpResponseRedirect, HttpResponsePermanentRedirect
from django.urls import include, path, re_path
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.static import serve
from django.views.decorators.csrf import csrf_exempt

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views_auth import login, logout, callback, whoami

from core.settings import MEDIA_ROOT, MEDIA_URL, STATIC_URL, STATIC_ROOT, DEVELOPMENT

    
def redirect_root(request):
    """
    Redirect browser requests to Swagger UI, API clients to continue normally
    """
    # for browsers, redirect to Swagger UI
    accept_header = request.META.get('HTTP_ACCEPT', '')
    if 'text/html' in accept_header: # is request from a browser?
        return HttpResponseRedirect('/api/swagger-ui/')
    
    # for API clients, redirect to schema
    return HttpResponseRedirect('/api/schema/')
    

@csrf_exempt
def redirect_to_v1(request, resource, suffix=None):
    """
    Redirect /api/{resource}{suffix} -> /api/v1/{resource}{suffix}
    - preserves trailing slash (if any) and any additional path suffix
    - preserves query parameters
    """
    suffix = suffix or ''
    url = f'/api/v1/{resource}{suffix}'
    qs = request.META.get('QUERY_STRING')
    if qs:
        url = f'{url}?{qs}'
    return HttpResponsePermanentRedirect(url)


urlpatterns = [

    # Django Admin
    path("admin/",           admin.site.urls),

    # API redirect for browsers
    re_path(r'^api/?$', redirect_root),
    
    # shortcuts and redirects
    re_path(r'^api/(?P<match>swagger|swagger-ui)/?$', lambda request, match: HttpResponsePermanentRedirect('/api/v1/swagger-ui')), # redirect to API Swagger UI
    re_path(r'^api/(?P<match>doc|docs|redoc)/?$',     lambda request, match: HttpResponsePermanentRedirect('/api/v1/redoc')), # redirect to API docs
    re_path(r'^api/(?P<match>schema)/?$',     lambda request, match: HttpResponsePermanentRedirect('/api/v1/schema')), # redirect to API schema

    # legacy redirects
    re_path(r'^api/(?P<resource>validationrequest|validationtask|validationoutcome|model)(?P<suffix>/.*)?$', redirect_to_v1),

    # API info + documentation
    path('api/v1/schema/',      SpectacularAPIView.as_view(), name='schema_v1'),
    path('api/v1/swagger-ui/',  SpectacularSwaggerView.as_view(url_name='schema_v1'), name='swagger-ui'),
    path('api/v1/redoc/',       SpectacularRedocView.as_view(url_name='schema_v1'), name='redoc'),

    # charts
    path('api/charts/',         include('apps.ifc_validation.chart_urls')), # Django Admin UI charts

    # APPS
    path('api/v1/',          include(('apps.ifc_validation.urls', 'apps.ifc_validation'), namespace='v1')), # API v1
    path('bff/',             include('apps.ifc_validation_bff.urls')), # BFF for UI

    # SQL Explorer
    path('sqlexplorer/',     include('explorer.urls')),

    # OAuth
    path('whoami/',          whoami, name='whoami'),
    path('login/',           login, name='login'),
    path('logout/',          logout, name='logout'),
    path('callback/',        callback, name='callback'),
]

if DEVELOPMENT:
    urlpatterns += [
        # redirect root to admin
        path("", lambda request: HttpResponseRedirect("/admin/")),
        # load debug toolbar
        path("__debug__/", include("debug_toolbar.urls")),
    ]

# securely serve uploaded files
# note: Django's default static() only works in DEBUG mode
urlpatterns += [
    re_path(
        r"^%s(?P<path>.*)$" % re.escape(MEDIA_URL.lstrip("/")),
        login_required(staff_member_required(serve)),
        kwargs={"document_root": MEDIA_ROOT},
    ),
]

# serve static files
# note: Django's default static() only works in DEBUG mode
urlpatterns += [
    re_path(
        r"^%s(?P<path>.*)$" % re.escape(STATIC_URL.lstrip("/")),
        serve,
        kwargs={"document_root": STATIC_ROOT},
    ),
]
