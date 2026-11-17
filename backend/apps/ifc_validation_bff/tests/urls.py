from django.urls import include, path

urlpatterns = [path("v2/", include("apps.ifc_validation_bff.ui.urls")),
               path("", include("apps.ifc_validation_bff.urls"))]
