from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, F, Avg, When, Case, DurationField
from django.db.models.functions import ExtractMonth, ExtractYear, Now, TruncDate, ExtractWeek
from django.http import JsonResponse
import calendar
import datetime

from apps.ifc_validation_models.models import (
    ValidationRequest,
    ValidationTask,
    UserAdditionalInfo,
    Model,
    AuthoringTool,
)

months = list(calendar.month_name)[1:] 

PERIODS = {
    "month": {
        "annotate": lambda qs: qs.annotate(period=ExtractMonth("created")),
        "label":   lambda row: months[row["period"] - 1],         
        "full_set": months,
    },
    "week": {
        "annotate": lambda qs: qs.annotate(period=ExtractWeek("created")),
        "label":   lambda row: f"W{int(row['period']):02d}",       # 1 → “W01”
        "full_set": [f"W{w:02d}" for w in range(1, 54)], # W01 - W53
    },
    "day": {
        "annotate": lambda qs: qs.annotate(period=TruncDate("created")),
        "label":   lambda row: row["period"].strftime("%Y-%m-%d"),
        "full_set": None,  
    },
}

COLORS = {
    "primary": "#79aec8",
    "success": "#55efc4",
    "danger": "#ff7675",
    "schema": "#25619e",
    "info": "#73d0d8",
    "header": "#88888",
    "norm_ia": "#efe255",
    "norm_ip": "#ff9f43",
    "industry": "#d373d8",
    "prereq": "#b4acb4",
    "digital_signatures": "#73d0d8",
    "inst_completion": "#e76565",
}

TASK_TYPES = {
    "SYNTAX": ("Syntax", COLORS["success"]),
    "HEADER_SYNTAX": ("Syntax", COLORS["success"]),
    "SYNTAX_HEADER": ("Syntax", COLORS["success"]),
    "SCHEMA": ("Schema", COLORS["schema"]),
    "INFO": ("Info", COLORS["info"]),
    "HEADER": ("Header", COLORS["header"]),
    "DIGITAL_SIGNATURES": ("Digital Signatures", COLORS["digital_signatures"]),
    "NORMATIVE_IA": ("Normative IA", COLORS["norm_ia"]),
    "NORMATIVE_IP": ("Normative IP", COLORS["norm_ip"]),
    "INDUSTRY": ("Industry", COLORS["industry"]),
    "PREREQ": ("Prereq", COLORS["prereq"]),
    "INST_COMPLETION": ("Inst Completion", COLORS["inst_completion"]),
}

SECONDS_PER_MINUTE = 60
BYTES_PER_MB = 1024 * 1024

def dict_for_period(period: str, year: int | None = None, window: int | None = None):
    """
    Return a {label: 0, …} dict whose keys are either:

    • The full fixed set (months / weeks / days in <year>)             – default
    • OR the last <window> periods counted backwards from <today>      – when window given
    """
    if window:                                   # rolling window branch
        return {lbl: 0 for lbl in _rolling_labels(period, window)}

    cfg = PERIODS[period]                  
    if cfg["full_set"] is not None:              # month / week
        return {lbl: 0 for lbl in cfg["full_set"]}

    first = datetime.date(year, 1, 1)
    last  = datetime.date(year, 12, 31)
    delta = datetime.timedelta(days=1)
    return { (first + i*delta).strftime("%Y-%m-%d"): 0
             for i in range((last - first).days + 1) }


def chart_response(title, labels, datasets):
    """Small wrapper around JsonResponse returning chart.js‑compatible payload."""
    return JsonResponse({
        "title": title,
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
    })
    
def group_by_period(qs, period, agg_key, agg_expression):
    cfg = PERIODS[period]
    qs = cfg["annotate"](qs)
    return (
        qs.values("period")
          .annotate(**{agg_key: agg_expression})
          .order_by("period")
    )

def fill_period_dict(grouped_qs, period, year, *, key, transform=lambda x: x, window=None):
    data = dict_for_period(period, year=year, window=window)   
    cfg  = PERIODS[period]

    for row in grouped_qs:
        label = cfg["label"](row)
        value = transform(row[key]) if row[key] is not None else 0
        if label in data:                                      
            data[label] = round(value, 2)
    return data

def get_period(request):
    return request.GET.get("period", "month").lower()

def get_window(request) -> int | None:
    try:
        w = int(request.GET.get("window", ""))
        return w if w > 0 else None
    except ValueError:
        return None


def _rolling_labels(period: str, window: int, today: datetime.date | None = None):
    """
    Build a chronologically ordered list of labels for the last <window> periods
    ending at <today> (date.today()).
    """
    today = today or datetime.date.today()

    if period == "day":
        return [
            (today - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(window - 1, -1, -1)
        ]

    if period == "week":
        week_start = today - datetime.timedelta(days=today.weekday())
        labels = []
        for _ in range(window):
            _, iso_week, _ = week_start.isocalendar()         
            labels.insert(0, f"W{iso_week:02d}")
            week_start -= datetime.timedelta(weeks=1)
        return labels
    month_cursor = today.replace(day=1) 
    labels = []
    for _ in range(window):
        labels.insert(0, months[month_cursor.month - 1])
        month_cursor = (month_cursor - datetime.timedelta(days=1)).replace(day=1)
    return labels


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
    period = get_period(request) 
    qs = ValidationRequest.objects.filter(created__year=year)

    success = group_by_period(qs.filter(status="COMPLETED"), period, "count", Count("id"))
    failed  = group_by_period(qs.filter(status="FAILED"), period,"count", Count("id"))

    
    success_dict = fill_period_dict(success, period, year, key="count", transform=int, window=get_window(request))
    failed_dict  = fill_period_dict(failed, period, year,  key="count", transform=int, window=get_window(request))

    return chart_response(
        title=f"Requests in {year}",
        labels=list(success_dict.keys()),
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

    grouped = group_by_period(qs, get_period(request), "avg_duration", Avg("_duration"))
    minutes_dict = fill_period_dict(
        grouped,
        get_period(request),
        year,
        key="avg_duration",
        transform=lambda d: (d.total_seconds() / SECONDS_PER_MINUTE) if d else 0,
        window=get_window(request)
    )

    return chart_response(
        title=f"Duration per request in {year}",
        labels=list(minutes_dict.keys()),
        datasets=[{
            "label": "Duration (avg, min)",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": list(minutes_dict.values()),
        }],
    )


@staff_member_required
def get_duration_per_task_chart(request, year):
    """
    Avg duration per task type, grouped by period (month/week/day).
    """
    period = get_period(request)

    qs = ValidationTask.objects.filter(created__year=year, status="COMPLETED").annotate(
        _duration=Case(
            When(ended__isnull=True, then=Now() - F("started")),
            default=F("ended") - F("started"),
            output_field=DurationField(),
        )
    )

    qs = PERIODS[period]["annotate"](qs)

    grouped = (
        qs.values("period", "type")
          .annotate(avg_duration=Avg("_duration"))
          .order_by("period", "type")
    )

    task_data = {t: dict_for_period(period, year) for t in TASK_TYPES}

    for row in grouped:
        task_type = row["type"]
        period_label = PERIODS[period]["label"](row)
        seconds = row["avg_duration"].total_seconds() if row["avg_duration"] else 0
        task_data[task_type][period_label] = round(seconds, 2)

    labels = list(task_data[next(iter(task_data))].keys())  # labels from any type

    datasets = []
    for t, (label, color) in TASK_TYPES.items():
        datasets.append({
            "label": label,
            "backgroundColor": color,
            "borderColor": COLORS["primary"],
            "data": [task_data[t][lbl] for lbl in labels],
        })

    return chart_response(
        title=f"Tasks in {year}",
        labels=labels,
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
    grouped = group_by_period(qs, get_period(request), "avg_size", Avg("size"))
    size_dict = fill_period_dict(
        grouped,
        get_period(request),
        year,
        key="avg_size",
        transform=lambda s: (s or 0) / BYTES_PER_MB,
        window=get_window(request)
    )

    return chart_response(
        title=f"Avg. Request Size in {year}",
        labels=list(size_dict.keys()),
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
    grouped = group_by_period(users_qs, get_period(request), "registrations", Count("id"))
    regs_dict = fill_period_dict(grouped, get_period(request), year, key="registrations", transform=int, window=get_window(request))

    return chart_response(
        title=f"New user registrations in {year}",
        labels=list(regs_dict.keys()),
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
    """
    Distinct uploaders per period, split into end-users vs vendors.
    """
    period = get_period(request)                     

    qs = ValidationRequest.objects.filter(created__year=year)

    total_qs = group_by_period(
        qs,
        period,
        "total",
        Count("created_by", distinct=True),
    )

    vendor_qs = group_by_period(
        qs.filter(created_by__useradditionalinfo__is_vendor=True),
        period,
        "vendors",
        Count("created_by", distinct=True),
    )

    total_dict  = fill_period_dict(total_qs,  period, year, key="total",  transform=int, window=get_window(request))
    vendor_dict = fill_period_dict(vendor_qs, period, year, key="vendors", transform=int, window=get_window(request))

    enduser_dict = {lbl: total_dict[lbl] - vendor_dict.get(lbl, 0)
                    for lbl in total_dict}

    labels = list(total_dict.keys())

    return chart_response(
        title=f"Uploaders (end-users vs vendors) in {year}",
        labels=labels,
        datasets=[
            {
                "label": "End users",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [enduser_dict[lbl] for lbl in labels],
                "stack": "stack1",
            },
            {
                "label": "Vendors",
                "backgroundColor": COLORS["success"],
                "borderColor": COLORS["success"],
                "data": [vendor_dict[lbl] for lbl in labels],
                "stack": "stack1",
            },
        ],
    )

@staff_member_required
def get_models_by_vendor_chart(request, year):
    """
    Count models uploaded per period, split by vendor vs end-user.
    """
    period = get_period(request)

    qs = Model.objects.filter(created__year=year).annotate(
        uploader_id=F("uploaded_by_id")
    )

    vendor_flags = _vendor_flag_map(
        qs.values_list("uploader_id", flat=True).distinct()
    )

    qs = PERIODS[period]["annotate"](qs)

    grouped = qs.values("period", "uploader_id")

    vendor_counts = dict_for_period(period, year)
    enduser_counts = dict_for_period(period, year)

    for row in grouped:
        uid = row["uploader_id"]
        period_label = PERIODS[period]["label"](row)

        if vendor_flags.get(uid):
            vendor_counts[period_label] += 1
        else:
            enduser_counts[period_label] += 1

    labels = list(vendor_counts.keys())

    return chart_response(
        title=f"Model uploads (vendors vs end-users) in {year}",
        labels=labels,
        datasets=[
            {
                "label": "End‑user models",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [enduser_counts[lbl] for lbl in labels],
                "stack": "stack1",
            },
            {
                "label": "Vendor models",
                "backgroundColor": COLORS["success"],
                "borderColor": COLORS["success"],
                "data": [vendor_counts[lbl] for lbl in labels],
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

    grouped = group_by_period(models_qs,
                            get_period(request),
                             "tools",
                             Count("produced_by", distinct=True))

    tools_dict = fill_period_dict(grouped,
                                   get_period(request),
                                   year,
                                   key="tools",
                                   transform=int, 
                                   window=get_window(request))

    return chart_response(
        title=f"Distinct authoring tools observed in {year}",
        labels=list(tools_dict.keys()),
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