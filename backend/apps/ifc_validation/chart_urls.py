from django.urls import path
from . import chart_views as charts


urlpatterns = [

    # Django Admin charts
    path("filter-options/", charts.get_filter_options),
    path("requests/<int:year>/", charts.get_requests_chart),
    path("duration-per-request/<int:year>/", charts.get_duration_per_request_chart),
    path("duration-per-task/<int:year>/", charts.get_duration_per_task_chart),
    path("uploads-per-2h/<int:year>/", charts.get_uploads_per_2h_chart),
    path("processing-status/<int:year>/", charts.get_processing_status_chart),
    path("avg-size/<int:year>/", charts.get_avg_size_chart),
    path("user-registrations/<int:year>/", charts.get_user_registrations_chart),
    path("usage-by-vendor/<int:year>/", charts.get_usage_by_vendor_chart),
    path("models-by-vendor/<int:year>/", charts.get_models_by_vendor_chart),
    path("top-tools/<int:year>/", charts.get_top_tools_chart),
    path("tools-count/<int:year>/", charts.get_tools_count_chart),
    path("totals/", charts.get_totals),
    path("queue-p95/<int:year>/", charts.get_queue_p95_chart),
    path("stuck-per-day/<int:year>/", charts.get_stuck_per_day_chart),
    path("uploads-per-weekday/<int:year>/", charts.get_uploads_per_weekday_chart),
]
