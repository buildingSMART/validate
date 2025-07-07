from django.urls import path

from .views import ValidationRequestListAPIView, ValidationRequestDetailAPIView
from .views import ValidationTaskListAPIView, ValidationTaskDetailAPIView
from .views import ValidationOutcomeListAPIView, ValidationOutcomeDetailAPIView
from .views import ModelListAPIView, ModelDetailAPIView

from . import chart_views as charts


urlpatterns = [

    # REST API
    path('validationrequest/',          ValidationRequestListAPIView.as_view()),
    path('validationrequest/<str:id>/', ValidationRequestDetailAPIView.as_view()),
    path('validationtask/',             ValidationTaskListAPIView.as_view()),
    path('validationtask/<str:id>/',    ValidationTaskDetailAPIView.as_view()),
    path('validationoutcome/',          ValidationOutcomeListAPIView.as_view()),
    path('validationoutcome/<str:id>/', ValidationOutcomeDetailAPIView.as_view()),
    path('model/',                      ModelListAPIView.as_view()),
    path('model/<str:id>/',             ModelDetailAPIView.as_view()),

    # Django Admin charts
    path("chart/filter-options/", charts.get_filter_options),
    path("chart/requests/<int:year>/", charts.get_requests_chart),
    path("chart/duration-per-request/<int:year>/", charts.get_duration_per_request_chart),
    path("chart/duration-per-task/<int:year>/", charts.get_duration_per_task_chart),
    path("chart/processing-status/<int:year>/", charts.get_processing_status_chart),
    path("chart/avg-size/<int:year>/", charts.get_avg_size_chart),
    path("chart/user-registrations/<int:year>/", charts.get_user_registrations_chart),
    path("chart/usage-by-vendor/<int:year>/", charts.get_usage_by_vendor_chart),
    path("chart/models-by-vendor/<int:year>/", charts.get_models_by_vendor_chart),
    path("chart/top-tools/<int:year>/", charts.get_top_tools_chart),
    path("chart/tools-count/<int:year>/", charts.get_tools_count_chart),
    path("chart/totals/", charts.get_totals),
]
