from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, F, Avg, When, Case, DurationField
from django.db.models.functions import ExtractMonth, ExtractYear, Now
from django.http import JsonResponse

from apps.ifc_validation_models.models import (
    ValidationRequest,
    ValidationTask,
    UserAdditionalInfo,
    Model,
    AuthoringTool,
)

months = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

COLORS = {
    "primary": "#79aec8",
    "success": "#55efc4",
    "danger": "#ff7675",
    "schema": "#25619e",
    "info": "#73d0d8",
    "norm_ia": "#efe255",
    "norm_ip": "#ff9f43",
    "industry": "#d373d8",
    "prereq": "#b4acb4",
    "inst_completion": "#e76565",
}

TASK_TYPES = {
    "SYNTAX": ("Syntax", COLORS["success"]),
    "SCHEMA": ("Schema", COLORS["schema"]),
    "INFO": ("Info", COLORS["info"]),
    "NORMATIVE_IA": ("Normative IA", COLORS["norm_ia"]),
    "NORMATIVE_IP": ("Normative IP", COLORS["norm_ip"]),
    "INDUSTRY": ("Industry", COLORS["industry"]),
    "PREREQ": ("Prereq", COLORS["prereq"]),
    "INST_COMPLETION": ("Inst Completion", COLORS["inst_completion"]),
}

SECONDS_PER_MINUTE = 60
BYTES_PER_MB = 1024 * 1024


def get_year_dict():
    """Return a template dict with month names as keys and 0 as default value."""
    return {m: 0 for m in months}


def chart_response(title, labels, datasets):
    """Small wrapper around JsonResponse returning chart.js‑compatible payload."""
    return JsonResponse({
        "title": title,
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
    })


def fill_monthly_dict(grouped_qs, key="value", transform=lambda x: x):
    """Convert an aggregated queryset (with month + <key>) into a {month: value} dict."""
    data = get_year_dict()
    for row in grouped_qs:
        month_name = months[row["month"] - 1]
        val = transform(row[key]) if row[key] is not None else 0
        data[month_name] = round(val, 2)
    return data


def group_by_month(qs, agg_key, agg_expression):
    """Annotate queryset with month & aggregate using *agg_expression* -> returns list of dicts."""
    return (
        qs.annotate(month=ExtractMonth("created"))
          .values("month")
          .annotate(**{agg_key: agg_expression})
          .order_by("month")
    )

@staff_member_required
def get_filter_options(request):
    """Return distinct years that have validation‑request activity (for dropdown filter)."""
    years = (
        ValidationRequest.objects
        .annotate(y=ExtractYear("created"))
        .values_list("y", flat=True)
        .distinct()
        .order_by("-y")
    )
    return JsonResponse({"options": list(years)})


@staff_member_required
def get_requests_chart(request, year):
    qs = ValidationRequest.objects.filter(created__year=year)

    success = group_by_month(qs.filter(status="COMPLETED"), "count", Count("id"))
    failed  = group_by_month(qs.filter(status="FAILED"),    "count", Count("id"))

    success_dict = fill_monthly_dict(success, key="count")
    failed_dict  = fill_monthly_dict(failed,  key="count")

    return chart_response(
        title=f"Requests in {year}",
        labels=months,
        datasets=[
            {
                "label": "Success",
                "backgroundColor": COLORS["success"],
                "borderColor": COLORS["primary"],
                "data": list(success_dict.values()),
            },
            {
                "label": "Failed",
                "backgroundColor": COLORS["danger"],
                "borderColor": COLORS["primary"],
                "data": list(failed_dict.values()),
            },
        ],
    )


@staff_member_required
def get_duration_per_request_chart(request, year):
    qs = ValidationRequest.objects.filter(created__year=year).annotate(
        _duration=Case(
            When(completed__isnull=True, then=Now() - F("started")),
            default=F("completed") - F("started"),
            output_field=DurationField(),
        )
    )

    grouped = group_by_month(qs, "avg_duration", Avg("_duration"))
    minutes_dict = fill_monthly_dict(
        grouped,
        key="avg_duration",
        transform=lambda d: (d.total_seconds() / SECONDS_PER_MINUTE) if d else 0,
    )

    return chart_response(
        title=f"Duration per request in {year}",
        labels=months,
        datasets=[{
            "label": "Duration (avg, min)",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": list(minutes_dict.values()),
        }],
    )


@staff_member_required
def get_duration_per_task_chart(request, year):
    qs = ValidationTask.objects.filter(created__year=year, status="COMPLETED").annotate(
        _duration=Case(
            When(ended__isnull=True, then=Now() - F("started")),
            default=F("ended") - F("started"),
            output_field=DurationField(),
        )
    )

    grouped = (
        qs.annotate(month=ExtractMonth("created"))
          .values("month", "type")
          .annotate(avg_duration=Avg("_duration"))
          .order_by("month", "type")
    )

    task_data = {t: get_year_dict() for t in TASK_TYPES}

    for row in grouped:
        task_type = row["type"]
        month_name = months[row["month"] - 1]
        seconds = row["avg_duration"].total_seconds() if row["avg_duration"] else 0
        task_data[task_type][month_name] = round(seconds, 2)

    datasets = []
    for t, (label, color) in TASK_TYPES.items():
        datasets.append({
            "label": label,
            "backgroundColor": color,
            "borderColor": COLORS["primary"],
            "data": list(task_data[t].values()),
        })

    return chart_response(
        title=f"Tasks in {year}",
        labels=months,
        datasets=datasets,
    )


@staff_member_required
def get_processing_status_chart(request, year):
    qs = ValidationRequest.objects.filter(created__year=year)
    completed = qs.filter(status="COMPLETED").count()
    failed    = qs.filter(status="FAILED").count()

    return chart_response(
        title=f"Processing success rate in {year}",
        labels=["Completed", "Failed"],
        datasets=[{
            "label": "Status",
            "backgroundColor": [COLORS["success"], COLORS["danger"]],
            "borderColor": [COLORS["success"], COLORS["danger"]],
            "data": [completed, failed],
        }],
    )


@staff_member_required
def get_avg_size_chart(request, year):
    qs = ValidationRequest.objects.filter(created__year=year)
    grouped = group_by_month(qs, "avg_size", Avg("size"))
    size_dict = fill_monthly_dict(
        grouped,
        key="avg_size",
        transform=lambda s: (s or 0) / BYTES_PER_MB,
    )

    return chart_response(
        title=f"Avg. Request Size in {year}",
        labels=months,
        datasets=[{
            "label": "Avg. Size (MB)",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": list(size_dict.values()),
        }],
    )


@staff_member_required
def get_user_registrations_chart(request, year):
    users_qs = UserAdditionalInfo.objects.filter(created__year=year)
    grouped = group_by_month(users_qs, "registrations", Count("id"))
    regs_dict = fill_monthly_dict(grouped, key="registrations", transform=int)

    return chart_response(
        title=f"New user registrations in {year}",
        labels=months,
        datasets=[{
            "label": "Registrations",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": list(regs_dict.values()),
        }],
    )


def _vendor_flag_map(user_ids):
    """Return {user_id: is_vendor} for the ids in *user_ids*."""
    return dict(
        UserAdditionalInfo.objects.filter(user_id__in=user_ids).values_list("user_id", "is_vendor")
    )


@staff_member_required
def get_usage_by_vendor_chart(request, year):
    qs = ValidationRequest.objects.filter(created__year=year)

    total_dict   = get_year_dict()
    vendor_dict  = get_year_dict()
    enduser_dict = get_year_dict()

    for m in range(1, 13):
        user_ids = qs.filter(created__month=m).values_list("created_by", flat=True).distinct()
        total = user_ids.count()

        vendor_flags = _vendor_flag_map(user_ids)
        vendors = sum(1 for uid in user_ids if vendor_flags.get(uid))

        label = months[m - 1]
        total_dict[label]   = total
        vendor_dict[label]  = vendors
        enduser_dict[label] = total - vendors

    return chart_response(
        title=f"Uploaders (end‑users vs vendors) in {year}",
        labels=months,
        datasets=[
            {
                "label": "End users",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": list(enduser_dict.values()),
                "stack": "stack1",
            },
            {
                "label": "Vendors",
                "backgroundColor": COLORS["success"],
                "borderColor": COLORS["success"],
                "data": list(vendor_dict.values()),
                "stack": "stack1",
            },
        ],
    )


@staff_member_required
def get_models_by_vendor_chart(request, year):
    models_qs = Model.objects.filter(created__year=year).annotate(
        month=ExtractMonth("created"),
        uploader_id=F("uploaded_by_id"),
    )

    vendor_flags = _vendor_flag_map(models_qs.values_list("uploader_id", flat=True))

    vendor_counts  = get_year_dict()
    enduser_counts = get_year_dict()

    for m in range(1, 13):
        month_models = models_qs.filter(month=m)
        v = e = 0
        for mdl in month_models:
            if vendor_flags.get(mdl.uploader_id):
                v += 1
            else:
                e += 1
        label = months[m - 1]
        vendor_counts[label]  = v
        enduser_counts[label] = e

    return chart_response(
        title=f"Model uploads (vendors vs end‑users) in {year}",
        labels=months,
        datasets=[
            {
                "label": "End‑user models",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": list(enduser_counts.values()),
                "stack": "stack1",
            },
            {
                "label": "Vendor models",
                "backgroundColor": COLORS["success"],
                "borderColor": COLORS["success"],
                "data": list(vendor_counts.values()),
                "stack": "stack1",
            },
        ],
    )


@staff_member_required
def get_top_tools_chart(request, year):
    agg = (
        Model.objects
        .filter(created__year=year, produced_by__isnull=False)
        .values("produced_by")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    if not agg:
        return chart_response(f"No uploads in {year}", [], [])

    tool_map = AuthoringTool.objects.in_bulk([row["produced_by"] for row in agg])
    labels = [tool_map[row["produced_by"]].full_name for row in agg]
    data   = [row["total"] for row in agg]

    return chart_response(
        title=f"Top 10 authoring tools in {year}",
        labels=labels,
        datasets=[{
            "label": "Models uploaded",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": data,
        }],
    )
    
    
@staff_member_required
def get_tools_count_chart(request, year):
    """
    Distinct authoring tools observed per month (Model.produced_by).
    """
    models_qs = Model.objects.filter(created__year=year,
                                     produced_by__isnull=False)

    grouped = group_by_month(models_qs,
                             "tools",
                             Count("produced_by", distinct=True))

    tools_dict = fill_monthly_dict(grouped,
                                   key="tools",
                                   transform=int)

    return chart_response(
        title=f"Distinct authoring tools observed in {year}",
        labels=months,
        datasets=[{
            "label": "Tools",
            "backgroundColor": COLORS["info"],
            "borderColor": COLORS["info"],
            "data": list(tools_dict.values()),
        }],
    )


@staff_member_required
def get_totals(request):
    # Overall, non time-split totals
    # choose one of the two lines for users:
    users_total = UserAdditionalInfo.objects.count()   # only fully-registered users
    # users_total = User.objects.count()                # or all auth users?

    files_total = ValidationRequest.objects.count()     # all validation requests
    tools_total = (
        Model.objects
             .filter(produced_by__isnull=False)
             .values("produced_by")
             .distinct()
             .count()
    )

    return JsonResponse({
        "users": users_total,
        "files": files_total,
        "tools": tools_total,
    })