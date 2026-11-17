from django.urls import include, path
from django.conf import settings

urlpatterns = [path("bff/", include("apps.ifc_validation_bff.urls")),
               path("" if settings.FRONTEND_MODE == "htmx" else "v2/", include("apps.ifc_validation_bff.ui.urls"))]
