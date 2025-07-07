# POC based on tutorial: https://testdriven.io/blog/django-charts

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Sum, Avg, When, Case, DurationField
from django.contrib.auth.models import User        
from django.db.models.functions import ExtractYear, ExtractMonth, Now, Coalesce, Concat
from django.http import JsonResponse

from apps.ifc_validation_models.models import ValidationRequest, ValidationTask, UserAdditionalInfo, Model, AuthoringTool

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
    validation_requests = validation_requests.annotate(
        _duration=Case(
            When(completed__isnull=True, then=Now() - F("started")),
            default=F("completed") - F("started"),
            output_field=DurationField(),
        ))
        
    grouped = (
        validation_requests
        .annotate(month=ExtractMonth("created"))
        .values("month")
        .annotate(average=Avg("_duration"))
        .order_by("month")
    )

    duration_per_request_dict = get_year_dict()
    SECONDS_PER_MINUTE = 60


    for group in grouped:
        avg_duration = group["average"]
        minutes = (avg_duration.total_seconds() / SECONDS_PER_MINUTE) if avg_duration else 0
        duration_per_request_dict[months[group["month"]-1]] = round(minutes, 2)

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
def get_duration_per_task_chart(request, year):

    # successful validation tasks
    validation_tasks = ValidationTask.objects.filter(created__year=year, status='COMPLETED')
    validation_tasks = validation_tasks.annotate(_duration=Case(
                When(ended__isnull=True, then=Now() - F('started')),
                default=F('ended') - F('started'),
                output_field=DurationField()
            ))
    grouped = validation_tasks.annotate(month=ExtractMonth("created")) \
        .values("month", "type") \
        .annotate(average=Avg("_duration")) \
        .values("month", "type", "average") \
        .order_by("month", "type")
    
    print(grouped)
    val_task_dict = dict()

    for type in ["SYNTAX", "SCHEMA", "INFO", "NORMATIVE_IA", "NORMATIVE_IP", "INDUSTRY", "PREREQ", "INST_COMPLETION"]:
        
        val_task_dict[type] = get_year_dict()

        for group in grouped:
            if group["type"] == type:
                avg_duration = group["average"]
                seconds = avg_duration.total_seconds() if avg_duration else 0
                month_name = months[group["month"] - 1]
                val_task_dict[type][month_name] = round(seconds, 2)

    return JsonResponse({
        "title": f"Tasks in {year}",
        "data": {
            "labels": months,
            "datasets": [{
                "label": "Syntax",
                "backgroundColor": colorSuccess,
                "borderColor": colorPrimary,
                "data": list(val_task_dict["SYNTAX"].values())
            },
            {
                "label": "Schema",
                "backgroundColor": "#25619e",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["SCHEMA"].values())
            },
            {
                "label": "Info",
                "backgroundColor": "#73d0d8",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["INFO"].values())
            },
            {
                "label": "Normative IA",
                "backgroundColor": "#efe255",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["NORMATIVE_IA"].values())
            },
            {
                "label": "Normative IP",
                "backgroundColor": "#ff9f43",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["NORMATIVE_IP"].values())
            },
            {
                "label": "Industry",
                "backgroundColor": "#d373d8",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["INDUSTRY"].values())
            },
            {
                "label": "Prereq",
                "backgroundColor": "#b4acb4",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["PREREQ"].values())
            },
            {
                "label": "Inst Completion",
                "backgroundColor": "#e76565",
                "borderColor": colorPrimary,
                "data": list(val_task_dict["INST_COMPLETION"].values())
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


@staff_member_required
def get_avg_size_chart(request, year):
    validation_requests = ValidationRequest.objects.filter(created__year=year)
    grouped = (
        validation_requests
        .annotate(month=ExtractMonth("created"))
        .values("month")
        .annotate(avg_size=Avg("size"))     
        .order_by("month")
    )


    size_dict = get_year_dict()
    BYTES_PER_MB = 1024 * 1024
    for group in grouped:
        avg_size_mb = (group["avg_size"] or 0) / BYTES_PER_MB
        size_dict[months[group["month"] - 1]] = round(avg_size_mb, 2) 

    return JsonResponse({
        "title": f"Avg. Request Size in {year}",
        "data": {
            "labels": list(size_dict.keys()),
            "datasets": [{
                "label": "Avg. Size (MB)",
                "backgroundColor": colorPrimary,
                "borderColor": colorPrimary,
                "data": list(size_dict.values())
            }]
        },
    })
    
@staff_member_required
def get_user_registrations_chart(request, year):
    """
    Returns the number of new (first-time) users per month.
    Uses the `created` timestamp of UserAdditionalInfo so that
    only users who finished the registration flow are counted.
    """
    users_qs = UserAdditionalInfo.objects.filter(created__year=year)

    grouped = (
        users_qs
        .annotate(month=ExtractMonth("created"))      
        .values("month")
        .annotate(registrations=Count("id"))
        .order_by("month")
    )

    regs_dict = get_year_dict()                      
    for group in grouped:
        regs_dict[months[group["month"] - 1]] = int(group["registrations"] or 0)

    return JsonResponse({
        "title": f"New user registrations in {year}",
        "data": {
            "labels": list(regs_dict.keys()),
            "datasets": [{
                "label": "Registrations",
                "backgroundColor": colorPrimary,
                "borderColor": colorPrimary,
                "data": list(regs_dict.values())
            }]
        },
    })

@staff_member_required
def get_usage_by_vendor_chart(request, year):
    """
    Count unique users per month, split into vendor vs non-vendor.
    Uses ValidationRequest.created_by as the 'uploader' field.
    """

    # all requests for this year
    qs = ValidationRequest.objects.filter(created__year=year)

    total_dict   = get_year_dict()   
    vendor_dict  = get_year_dict()   
    enduser_dict = get_year_dict() 

    for month_num in range(1, 13):
        # distinct user IDs that uploaded in this month
        user_ids = (
            qs.filter(created__month=month_num)
              .values_list("created_by", flat=True)
              .distinct()
        )

        total = user_ids.count()

        # distinct vendor IDs among them
        vendor_ids = (
            UserAdditionalInfo.objects
                .filter(user_id__in=user_ids, is_vendor=True)
                .values_list("user_id", flat=True)
                .distinct()
        )
        vendors = vendor_ids.count()

        label = months[month_num - 1]
        total_dict[label]   = int(total)
        vendor_dict[label]  = int(vendors)
        enduser_dict[label] = int(total - vendors)

    return JsonResponse({
        "title": f"Uploaders (end-users vs vendors) in {year}",
        "data": {
            "labels": list(total_dict.keys()),
            "datasets": [
                {
                    "label": "End users",
                    "backgroundColor": colorPrimary,
                    "borderColor": colorPrimary,
                    "data": list(enduser_dict.values()),
                    "stack": "stack1",
                },
                {
                    "label": "Vendors",
                    "backgroundColor": colorSuccess,
                    "borderColor": colorSuccess,
                    "data": list(vendor_dict.values()),
                    "stack": "stack1",
                },
            ],
        },
    })


@staff_member_required
def get_models_by_vendor_chart(request, year):
    """
    Count models uploaded per month, divided into vendor vs non-vendor.
    Uses Model.created for the month, Model.uploaded_by for the user,
    and UserAdditionalInfo.is_vendor to decide the bucket.
    """

    # All models created in the selected year
    models_qs = Model.objects.filter(created__year=year).annotate(
        month=ExtractMonth("created"),
        uploader_id=F("uploaded_by_id"),
    )

    # pre-fetch vendor flags in one query
    vendor_map = dict(
        UserAdditionalInfo.objects.filter(user_id__in=models_qs.values_list("uploader_id", flat=True))
        .values_list("user_id", "is_vendor")
    )

    vendor_counts  = get_year_dict()
    enduser_counts = get_year_dict()

    for m in range(1, 13):
        month_models = models_qs.filter(month=m)

        vendors = 0
        endusers = 0
        for mdl in month_models:
            if vendor_map.get(mdl.uploader_id):
                vendors += 1
            else:
                endusers += 1

        label = months[m-1]
        vendor_counts[label]  = vendors
        enduser_counts[label] = endusers

    return JsonResponse({
        "title": f"Model uploads (vendors vs end-users) in {year}",
        "data": {
            "labels": list(vendor_counts.keys()),
            "datasets": [
                {
                    "label": "End-user models",
                    "backgroundColor": colorPrimary,
                    "borderColor": colorPrimary,
                    "data": list(enduser_counts.values()),
                    "stack": "stack1",
                },
                {
                    "label": "Vendor models",
                    "backgroundColor": colorSuccess,
                    "borderColor": colorSuccess,
                    "data": list(vendor_counts.values()),
                    "stack": "stack1",
                },
            ],
        },
    })

@staff_member_required
def get_top_tools_chart(request, year):
    """
    Returns the ten authoring tools that uploaded the most models in <year>.
    """

    # aggregate per tool ID
    agg = (
        Model.objects
        .filter(created__year=year, produced_by__isnull=False)
        .values("produced_by")                 # authoring-tool primary-key
        .annotate(total=Count("id"))           # how many models
        .order_by("-total")[:10]               # top 10
    )

    if not agg:
        return JsonResponse({
            "title": f"No uploads in {year}",
            "data": {"labels": [], "datasets": []},
        })

    # 2. fetch names once 
    tool_map = AuthoringTool.objects.in_bulk([row["produced_by"] for row in agg])

    labels = [tool_map[row["produced_by"]].full_name for row in agg]
    data   = [row["total"] for row in agg]

    return JsonResponse({
        "title": f"Top 10 authoring tools in {year}",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Models uploaded",
                "backgroundColor": colorPrimary,
                "borderColor": colorPrimary,
                "data": data,
            }]
        },
    })
