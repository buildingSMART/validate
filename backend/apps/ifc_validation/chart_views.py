# POC based on tutorial: https://testdriven.io/blog/django-charts

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Sum, Avg, When, Case, DurationField
from django.db.models.functions import ExtractYear, ExtractMonth, Now
from django.http import JsonResponse

from apps.ifc_validation_models.models import ValidationRequest

months = [
    "January", 
    "February", 
    "March", 
    "April",
    "May", 
    "June", 
    "July", 
    "August",
    "September", 
    "October", 
    "November", 
    "December"
]
colorPrimary, colorSuccess, colorDanger = "#79aec8", "#55efc4", "#ff7675"

def get_year_dict():
    year_dict = dict()

    for month in months:
        year_dict[month] = 0

    return year_dict


@staff_member_required
def get_filter_options(request):
    validation_requests = ValidationRequest.objects.all()
    validation_requests = validation_requests.annotate(year=ExtractYear("created")).values("year").order_by("-year").distinct()
    options = [val_request["year"] for val_request in validation_requests]

    return JsonResponse({
        "options": options,
    })


@staff_member_required
def get_requests_chart(request, year):

    # successful validation requests
    validation_requests = ValidationRequest.objects.filter(created__year=year, status='COMPLETED')
    grouped = validation_requests.annotate(price=F("size")).annotate(month=ExtractMonth("created"))\
        .values("month").annotate(average=Count("size")).values("month", "average").order_by("month")
    
    # failed validation requests
    failed_validation_requests = ValidationRequest.objects.filter(created__year=year, status='FAILED')
    failed_grouped = failed_validation_requests.annotate(price=F("size")).annotate(month=ExtractMonth("created"))\
        .values("month").annotate(average=Count("size")).values("month", "average").order_by("month")

    val_req_dict = get_year_dict()
    val_req_dict2 = get_year_dict()

    for group in grouped:
        val_req_dict[months[group["month"]-1]] = round(group["average"], 2)

    for group in failed_grouped:
        val_req_dict2[months[group["month"]-1]] = round(group["average"], 2)

    return JsonResponse({
        "title": f"Requests in {year}",
        "data": {
            "labels": list(val_req_dict.keys()),
            "datasets": [{
                "label": "Success",
                "backgroundColor": colorSuccess,
                "borderColor": colorPrimary,
                "data": list(val_req_dict.values())
            },
            {
                "label": "Failed",
                "backgroundColor": colorDanger,
                "borderColor": colorPrimary,
                "data": list(val_req_dict2.values())
            }]
        },
    })


@staff_member_required
def get_duration_per_request_chart(request, year):
    validation_requests = ValidationRequest.objects.filter(created__year=year)
    validation_requests = validation_requests.annotate(_duration=Case(
                When(completed__isnull=True, then=Now() - F('started')),
                default=F('completed') - F('started'),
                output_field=DurationField()
            ))
    grouped_purchases = validation_requests.annotate(month=ExtractMonth("created"))\
        .values("month").annotate(average=Avg("_duration")).values("month", "average").order_by("month")

    duration_per_request_dict = get_year_dict()

    for group in grouped_purchases:
        avg_duration = group["average"]
        seconds = avg_duration.total_seconds() if avg_duration else 0
        duration_per_request_dict[months[group["month"]-1]] = round(seconds, 2)

    return JsonResponse({
        "title": f"Duration per request in {year}",
        "data": {
            "labels": list(duration_per_request_dict.keys()),
            "datasets": [{
                "label": "Duration (avg)",
                "backgroundColor": colorPrimary,
                "borderColor": colorPrimary,
                "data": list(duration_per_request_dict.values()),
            }]
        },
    })


@staff_member_required
def get_processing_status_chart(request, year):
    validation_requests = ValidationRequest.objects.filter(created__year=year)

    return JsonResponse({
        "title": f"Processing success rate in {year}",
        "data": {
            "labels": ["Completed", "Failed"],
            "datasets": [{
                "label": "Status",
                "backgroundColor": [colorSuccess, colorDanger],
                "borderColor": [colorSuccess, colorDanger],
                "data": [
                    validation_requests.filter(status='COMPLETED').count(),
                    validation_requests.filter(status='FAILED').count(),
                ],
            }]
        },
    })