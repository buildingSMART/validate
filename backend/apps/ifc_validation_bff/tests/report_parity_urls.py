from django.urls import include, path

urlpatterns = [path("bff/", include("apps.ifc_validation_bff.urls")),
               path("v2/", include("apps.ifc_validation_bff.ui.urls"))]
