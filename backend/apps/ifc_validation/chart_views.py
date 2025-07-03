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
colorPalette = ["#55efc4", "#81ecec", "#a29bfe", "#ffeaa7", "#fab1a0", "#ff7675", "#fd79a8"]
colorPrimary, colorSuccess, colorDanger = "#79aec8", colorPalette[0], colorPalette[5]

def get_year_dict():
    year_dict = dict()

    for month in months:
        year_dict[month] = 0

    return year_dict


def generate_color_palette(amount):
    palette = []

    i = 0
    while i < len(colorPalette) and len(palette) < amount:
        palette.append(colorPalette[i])
        i += 1
        if i == len(colorPalette) and len(palette) < amount:
            i = 0

    return palette


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
    validation_requests = ValidationRequest.objects.filter(created__year=year, status='COMPLETED')
    grouped = validation_requests.annotate(price=F("size")).annotate(month=ExtractMonth("created"))\
        .values("month").annotate(average=Count("size")).values("month", "average").order_by("month")

    sales_dict = get_year_dict()

    for group in grouped:
        sales_dict[months[group["month"]-1]] = round(group["average"], 2)

    return JsonResponse({
        "title": f"Requests in {year}",
        "data": {
            "labels": list(sales_dict.keys()),
            "datasets": [{
                "label": "Count",
                "backgroundColor": colorPrimary,
                "borderColor": colorPrimary,
                "data": list(sales_dict.values()),
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