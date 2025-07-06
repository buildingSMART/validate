from django.urls import path

from .views import ValidationRequestListAPIView, ValidationRequestDetailAPIView
from .views import ValidationTaskListAPIView, ValidationTaskDetailAPIView
from .views import ValidationOutcomeListAPIView, ValidationOutcomeDetailAPIView
from .views import ModelListAPIView, ModelDetailAPIView

from .chart_views import get_filter_options
from .chart_views import get_requests_chart
from .chart_views import get_duration_per_request_chart
from .chart_views import get_processing_status_chart
from .chart_views import get_duration_per_task_chart

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
    path("chart/filter-options/", get_filter_options),
    path("chart/requests/<int:year>/", get_requests_chart),
    path("chart/duration-per-request/<int:year>/", get_duration_per_request_chart),
    path("chart/duration-per-task/<int:year>/", get_duration_per_task_chart),
    path("chart/processing-status/<int:year>/", get_processing_status_chart),
]
