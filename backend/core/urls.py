import re
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import include, path, re_path
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.static import serve
from django.views import View

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views_auth import login, logout, callback, whoami

from core.settings import MEDIA_ROOT, MEDIA_URL, STATIC_URL, STATIC_ROOT, DEVELOPMENT

class APIRedirectView(View):
    """
    Redirect browser requests to Swagger UI, API clients to continue normally
    """
    def get(self, request, *args, **kwargs):
        
        # for browsers, redirect to Swagger UI
        accept_header = request.META.get('HTTP_ACCEPT', '') 
        if 'text/html' in accept_header: # is request from a browser?
            return HttpResponseRedirect('/api/swagger-ui/')
        
        # for API clients, redirect to schema
        return HttpResponseRedirect('/api/schema/')

urlpatterns = [

    # Django Admin
    path("admin/",           admin.site.urls),

    # API redirect for browsers
    path('api/',             APIRedirectView.as_view(), name='api-redirect'),

    # API info + documentation
    path('api/schema/',      SpectacularAPIView.as_view(), name='schema'),
    path('api/swagger-ui/',  SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',       SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # APPS
    path('api/',             include('apps.ifc_validation.urls')),      # API
    path('bff/',             include('apps.ifc_validation_bff.urls')),  # BFF

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
