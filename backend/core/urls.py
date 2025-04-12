from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views_auth import login, logout, callback, whoami

from core.settings import MEDIA_ROOT, MEDIA_URL, STATIC_URL, STATIC_ROOT

urlpatterns = [

    # Django Admin
    path("admin/",           admin.site.urls),

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

    # Debug toolbar
    path("__debug__/",       include("debug_toolbar.urls")),
]

# serving uploaded files
urlpatterns += static(MEDIA_URL, document_root=MEDIA_ROOT)

# serve static files
urlpatterns += static(STATIC_URL, document_root=STATIC_ROOT)
