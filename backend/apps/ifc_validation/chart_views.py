from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, F, Avg, When, Case, DurationField, IntegerField, ExpressionWrapper, Exists, OuterRef
from django.db.models.functions import ExtractMonth, ExtractYear, Now, TruncDate, ExtractWeek, ExtractHour, Trunc, ExtractWeekDay, Cast
from django.http import JsonResponse

from zoneinfo import ZoneInfo
import math
import calendar
import datetime
import re

from apps.ifc_validation_models.models import (
    ValidationRequest,
    ValidationTask,
    UserAdditionalInfo,
    Model,
    AuthoringTool,
)

MONTHS = list(calendar.month_name)[1:] 

PERIODS = {
    "month": {
        "annotate": lambda qs: qs.annotate(period=ExtractMonth("created")),
        "label":   lambda row: MONTHS[row["period"] - 1],         
        "full_set": MONTHS,
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
    "quarter": {
            "annotate": lambda qs: qs.annotate(
                month=ExtractMonth("created")
            ).annotate(
                period=Case(
                    When(month__in=[1, 2, 3], then=1),
                    When(month__in=[4, 5, 6], then=2),
                    When(month__in=[7, 8, 9], then=3),
                    When(month__in=[10, 11, 12], then=4),
                    output_field=IntegerField(),
                )
            ),
            "label": lambda row: f"Q{row['period']}",
            "full_set": [f"Q{q}" for q in range(1, 5)],
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

SYNTAX_TASK_TYPES = {
    "SYNTAX_HEADER": "SYNTAX",
    "HEADER_SYNTAX": "SYNTAX",
}

TASK_TYPES = {
    "SYNTAX": ("Syntax", COLORS["success"]),
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

SCHEMA_COLORS = {
    "IFC2X3": COLORS["norm_ia"],
    "IFC4": COLORS["success"],
    "IFC4X3": COLORS["info"],
    "UNKNOWN": COLORS["prereq"],  
}

def normalize_schema(schema: str | None) -> str | None:
    """
    Map various schema strings to one of our canonical buckets:
    IFC2X3, IFC4, IFC4X3, or None (for 'unknown/other').

    Examples that end up as IFC4X3:
      - "IFC4X3"
      - "IFC4X3_ADD1"
      - "IFC4X3_ADD2"
    """
    s = (schema or "").upper()

    if "IFC4X3" in s:
        return "IFC4X3"
    if s.startswith("IFC4"):
        return "IFC4"
    if s.startswith("IFC2X3"):
        return "IFC2X3"
    return None


SECONDS_PER_MINUTE = 60
BYTES_PER_MB = 1024 * 1024

def dict_for_period(period: str, year: int | None = None, window: int | None = None):
    """
    Return a {label: 0, …} dict whose keys are either:

    • The full fixed set (months / weeks / days in <year>)             – default
    • OR the last <window> periods counted backwards from <today>      – when window given
    """
    if window:                                   
        return {lbl: 0 for lbl in _rolling_labels(period, window)}

    cfg = PERIODS[period]                  
    if cfg["full_set"] is not None:              
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


def group_by_period(qs, period, agg_key, agg_expression, window=None):
    cfg = PERIODS[period]
    qs = cfg["annotate"](qs)
    
    if window:
        valid_labels = set(_rolling_labels(period, window))

        qs = qs.filter(
            Q(period__in=[
                int(lbl[1:]) if period in ["week", "quarter"]
                else MONTHS.index(lbl) + 1 if period == "month"
                else lbl
                for lbl in valid_labels
            ])
        )
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

    if period == "quarter":
        current_quarter = (today.month - 1) // 3 + 1
        current_year = today.year
        labels = []
        for _ in range(window):
            labels.insert(0, f"Q{current_quarter}")
            current_quarter -= 1
            if current_quarter == 0:
                current_quarter = 4
                current_year -= 1
        return labels
    
    month_cursor = today.replace(day=1) 
    labels = []
    for _ in range(window):
        labels.insert(0, MONTHS[month_cursor.month - 1])
        month_cursor = (month_cursor - datetime.timedelta(days=1)).replace(day=1)
    return labels


def _top_tools_chart_response(qs, period, year, title_prefix):
    """
    Helper to build a 'top 10 authoring tools' chart response
    for a given queryset of Models.
    """
    # Aggregate models per AuthoringTool first
    agg = (
        qs.values("produced_by")
          .annotate(total=Count("id"))
    )

    if not agg:
        title = f"No uploads in {year}" if period != "total" else "No uploads (Total)"
        return chart_response(title, [], [])

    tool_map = AuthoringTool.objects.in_bulk([row["produced_by"] for row in agg])

    # Group by *normalised* label
    buckets: dict[str, int] = {}
    for row in agg:
        tool = tool_map.get(row["produced_by"])
        if not tool:
            continue
        label = normalize_tool_label(tool)
        buckets[label] = buckets.get(label, 0) + (row["total"] or 0)

    # Take top 10 labels by total
    sorted_items = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)[:10]
    labels = [label for label, _ in sorted_items]
    data   = [total for _, total in sorted_items]

    title = (
        f"{title_prefix} in {year}"
        if period != "total"
        else f"{title_prefix} (Total)"
    )

    return chart_response(
        title=title,
        labels=labels,
        datasets=[{
            "label": "Models uploaded",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": data,
        }],
    )

    
def normalize_tool_label(tool: AuthoringTool) -> str:
    """
    Map AuthoringTool instances to a display label that groups:
    - Revit by year (Revit 2025, Revit 2024, …)
    - All Quadri tools into a single 'Quadri (all)' bucket
    - All Washington State tools into 'Washington State (all)'
    Otherwise: keep the original full_name.
    """
    name = tool.full_name or ""
    up = name.upper()

    # Quadri → one bucket
    if "QUADRI" in up:
        return "Quadri"

    # Washington State → one bucket
    if "WASHINGTON STATE" in up:
        return "Washington State Department"
    
    if "ACCA" in up:
        return "ACCA"
    
    if "Civil3D" in up:
        return "Civil3D"
    
    if "BricsCAD" in up:
        return "BricsCAD"
    
    if "Bocad Steel" in up:
        return "Bocad Steel"
    
    if "Civil Designer" in up:
        return "Civil Designer"
    
    if "sketchup" in up.lower():
        return "Trimble SketchUp"

    # Revit → group by year
    if "REVIT" in up:
        # Look for a 4-digit year such as 2025, 2024, ...
        m = re.search(r"(20\d{2})", name)
        if m:
            year = m.group(1)
            return f"Revit {year}"
        return "Revit (other)"

    # Fallback: keep the tool name as-is
    return name


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
def get_requests_total_chart(request, year):
    """
    Total number of validation requests (no status split).
    """
    period = get_period(request)
    window = get_window(request)

    # ---------------------------
    # TOTAL VIEW (all years)
    # ---------------------------
    if period == "total":
        total = ValidationRequest.objects.count()

        return chart_response(
            title="Total requests (all years)",
            labels=["Total"],
            datasets=[{
                "label": "Requests",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [total],
            }],
        )

    # ---------------------------
    # TIME-SPLIT VIEW
    # ---------------------------
    qs = ValidationRequest.objects.all()
    if not window:
        qs = qs.filter(created__year=year)

    grouped = group_by_period(
        qs,
        period,
        "count",
        Count("id"),
        window=window,
    )

    total_dict = fill_period_dict(
        grouped,
        period,
        year,
        key="count",
        transform=int,
        window=window,
    )

    return chart_response(
        title=f"Total requests in {year}",
        labels=list(total_dict.keys()),
        datasets=[{
            "label": "Requests",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": list(total_dict.values()),
        }],
    )
    

@staff_member_required
def get_requests_chart(request, year):
    period = get_period(request)
    window = get_window(request)

    if period == "total":
        qs = ValidationRequest.objects.all()

        success_count = qs.filter(status="COMPLETED").count()
        failed_count  = qs.filter(status="FAILED").count()

        return chart_response(
            title="Total requests (all years)",
            labels=["Success", "Failed"],
            datasets=[{
                "label": "Requests",
                "backgroundColor": [COLORS["success"], COLORS["danger"]],
                "borderColor": [COLORS["success"], COLORS["danger"]],
                "data": [success_count, failed_count],
            }]
        )

    qs = ValidationRequest.objects.filter(created__year=year)

    success_qs = group_by_period(qs.filter(status="COMPLETED"), period, "count", Count("id"), window=window)
    failed_qs  = group_by_period(qs.filter(status="FAILED"), period, "count", Count("id"), window=window)

    success_dict = fill_period_dict(success_qs, period, year, key="count", transform=int, window=window)
    failed_dict  = fill_period_dict(failed_qs,  period, year, key="count", transform=int, window=window)

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
def get_requests_by_schema_chart(request, year):
    """
    Number of validation requests, split by IFC schema (IFC2X3, IFC4, IFC4X3).
    """
    period = get_period(request)
    window = get_window(request)

    # Base queryset: only requests that have a model
    qs = ValidationRequest.objects.filter(model__isnull=False)

    # For non-total views (month/week/day/quarter), limit to the given year
    if period != "total" and not window:
        qs = qs.filter(created__year=year)

    # ------------------------------------------------------------------
    # TOTAL VIEW (no time splitting, just counts per schema)
    # ------------------------------------------------------------------
    if period == "total":
        agg = (
            qs.values("model__schema")
              .annotate(total=Count("id"))
              .order_by("model__schema")
        )

        # Only track the 3 known schemas
        buckets = {"IFC2X3": 0, "IFC4": 0, "IFC4X3": 0}
        for row in agg:
            key = normalize_schema(row["model__schema"])
            if not key:
                continue  # skip UNKNOWN / anything else

            buckets[key] += row["total"] or 0

        labels = ["IFC2X3", "IFC4", "IFC4X3"]
        data = [
            buckets["IFC2X3"],
            buckets["IFC4"],
            buckets["IFC4X3"],
        ]

        return chart_response(
            title="Requests by IFC schema (Total)",
            labels=labels,
            datasets=[{
                "label": "Requests",
                "backgroundColor": [
                    SCHEMA_COLORS["IFC2X3"],
                    SCHEMA_COLORS["IFC4"],
                    SCHEMA_COLORS["IFC4X3"],
                ],
                "borderColor": [
                    SCHEMA_COLORS["IFC2X3"],
                    SCHEMA_COLORS["IFC4"],
                    SCHEMA_COLORS["IFC4X3"],
                ],
                "data": data,
            }],
        )

    # ------------------------------------------------------------------
    # TIME-SPLIT VIEW (month/week/day/quarter) – stacked per schema
    # ------------------------------------------------------------------

    # Annotate with chosen period
    annotated_qs = PERIODS[period]["annotate"](qs)

    # Apply rolling window filter if requested
    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated_qs = annotated_qs.filter(period__in=label_values)

    # Group by period + schema
    grouped = (
        annotated_qs
        .values("period", "model__schema")
        .annotate(total=Count("id"))
        .order_by("period", "model__schema")
    )

    # Prepare per-schema dicts keyed by period label
    schema_keys = ["IFC2X3", "IFC4", "IFC4X3"]
    schema_data = {
        key: dict_for_period(period, year, window=window)
        for key in schema_keys
    }

    for row in grouped:
        key = normalize_schema(row["model__schema"])
        if not key:
            continue  # skip UNKNOWN / anything else

        period_label = PERIODS[period]["label"](row)
        if period_label not in schema_data[key]:
            # Shouldn't really happen because dict_for_period built the keys,
            # but guard just in case.
            continue

        schema_data[key][period_label] += int(row["total"] or 0)

    # Labels = period labels (same for all buckets)
    labels = list(next(iter(schema_data.values())).keys()) if schema_data else []

    datasets = [
        {
            "label": "IFC2X3",
            "backgroundColor": SCHEMA_COLORS["IFC2X3"],
            "borderColor": COLORS["primary"],
            "data": [schema_data["IFC2X3"][lbl] for lbl in labels],
            "stack": "stack1",
        },
        {
            "label": "IFC4",
            "backgroundColor": SCHEMA_COLORS["IFC4"],
            "borderColor": COLORS["primary"],
            "data": [schema_data["IFC4"][lbl] for lbl in labels],
            "stack": "stack1",
        },
        {
            "label": "IFC4X3",
            "backgroundColor": SCHEMA_COLORS["IFC4X3"],
            "borderColor": COLORS["primary"],
            "data": [schema_data["IFC4X3"][lbl] for lbl in labels],
            "stack": "stack1",
        },
    ]

    return chart_response(
        title=f"Requests by IFC schema in {year}",
        labels=labels,
        datasets=datasets,
    )


@staff_member_required
def get_duration_per_request_chart(request, year):
    'Total average request duration'
    period = get_period(request)
    window = get_window(request)

    if period == "total":
        qs = ValidationRequest.objects.annotate(
            _duration=Case(
                When(completed__isnull=True, then=Now() - F("started")),
                default=F("completed") - F("started"),
                output_field=DurationField(),
            )
        )

        avg_duration = qs.aggregate(avg_duration=Avg("_duration"))["avg_duration"]
        minutes = (avg_duration.total_seconds() / SECONDS_PER_MINUTE) if avg_duration else 0

        return chart_response(
            title="Avg. duration per request (Total)",
            labels=["Total"],
            datasets=[{
                "label": "Avg Duration (min)",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [round(minutes, 2)],
            }]
        )

    qs = ValidationRequest.objects.all()
    if not window:
        qs = qs.filter(created__year=year)

    qs = qs.annotate(
        _duration=Case(
            When(completed__isnull=True, then=Now() - F("started")),
            default=F("completed") - F("started"),
            output_field=DurationField(),
        )
    )

    grouped = group_by_period(qs, period, "avg_duration", Avg("_duration"), window=window)
    minutes_dict = fill_period_dict(
        grouped,
        period,
        year,
        key="avg_duration",
        transform=lambda d: (d.total_seconds() / SECONDS_PER_MINUTE) if d else 0,
        window=window
    )

    return chart_response(
        title=f"Duration per request in {year}",
        labels=list(minutes_dict.keys()),
        datasets=[{
            "label": "Avg Duration (min)",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": list(minutes_dict.values()),
        }],
    )


@staff_member_required
def get_duration_per_task_chart(request, year):
    """
    Avg duration per task type, grouped by period or aggregated as 'total'.

    """
    period = get_period(request)
    window = get_window(request)

    qs = ValidationTask.objects.filter(status="COMPLETED")

    if period != "total":
        qs = qs.filter(created__year=year)

    qs = qs.annotate(
        _duration=Case(
            When(ended__isnull=True, then=Now() - F("started")),
            default=F("ended") - F("started"),
            output_field=DurationField(),
        )
    )

    if period == "total":
        grouped = (
            qs.values("type")
              .annotate(avg_duration=Avg("_duration"))
              .order_by("type")
        )

        datasets = []
        labels = ["Total"]
        for row in grouped:
            original_type = row["type"]
            task_type = SYNTAX_TASK_TYPES.get(original_type, original_type)

            if task_type not in TASK_TYPES:
                continue

            seconds = row["avg_duration"].total_seconds() if row["avg_duration"] else 0
            datasets.append({
                "label": TASK_TYPES[task_type][0],
                "backgroundColor": TASK_TYPES[task_type][1],
                "borderColor": COLORS["primary"],
                "data": [round(seconds, 2)],
            })

        return chart_response(
            title="Avg Task Duration (Total)",
            labels=labels,
            datasets=datasets,
        )

    annotated_qs = PERIODS[period]["annotate"](qs)
    
    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated_qs = annotated_qs.filter(period__in=label_values)

    grouped = (
        annotated_qs.values("period", "type")
        .annotate(avg_duration=Avg("_duration"))
        .order_by("period", "type")
    )

    task_data = {}

    for row in grouped:
        original_type = row["type"]
        task_type = SYNTAX_TASK_TYPES.get(original_type, original_type)

        if task_type not in TASK_TYPES:
            continue

        if task_type not in task_data:
            task_data[task_type] = dict_for_period(period, year, window=window)

        period_label = PERIODS[period]["label"](row)
        seconds = row["avg_duration"].total_seconds() if row["avg_duration"] else 0
        task_data[task_type][period_label] += round(seconds, 2)

    labels = list(next(iter(task_data.values())).keys()) if task_data else []

    datasets = [
        {
            "label": TASK_TYPES[t][0],
            "backgroundColor": TASK_TYPES[t][1],
            "borderColor": COLORS["primary"],
            "data": [task_data[t][lbl] for lbl in labels],
        }
        for t in task_data 
    ]

    return chart_response(
        title=f"Duration per Task in {year}",
        labels=labels,
        datasets=datasets,
    )


@staff_member_required
def get_processing_status_chart(request, year):
    period = get_period(request)

    if period == "total":
        qs = ValidationRequest.objects.all()
        title = "Processing success rate (Total)"
    else:
        qs = ValidationRequest.objects.filter(created__year=year)
        title = f"Processing success rate in {year}"

    completed = qs.filter(status="COMPLETED").count()
    failed    = qs.filter(status="FAILED").count()

    return chart_response(
        title=title,
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
    window=get_window(request)
    period = get_period(request)

    if period == "total":
        avg_size = ValidationRequest.objects.aggregate(avg_size=Avg("size"))["avg_size"]
        size_mb = (avg_size or 0) / BYTES_PER_MB

        return chart_response(
            title="Avg. Request Size (Total)",
            labels=["Total"],
            datasets=[{
                "label": "Avg. Size (MB)",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [round(size_mb, 2)],
            }],
        )

    qs = ValidationRequest.objects.filter(created__year=year)
    grouped = group_by_period(qs, period, "avg_size", Avg("size"), window=window)
    size_dict = fill_period_dict(
        grouped,
        period,
        year,
        key="avg_size",
        transform=lambda s: (s or 0) / BYTES_PER_MB,
        window=window
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
    window=get_window(request)
    period = get_period(request)

    if period == "total":
        total = UserAdditionalInfo.objects.count()

        return chart_response(
            title="User Registrations (Total)",
            labels=["Total"],
            datasets=[{
                "label": "Registrations",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [total],
            }],
        )

    users_qs = UserAdditionalInfo.objects.filter(created__year=year)
    grouped = group_by_period(users_qs, period, "registrations", Count("id"), window=window)
    regs_dict = fill_period_dict(
        grouped,
        period,
        year,
        key="registrations",
        transform=int,
        window=window
    )

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

@staff_member_required
def get_active_user_registrations_chart(request, year):
    """
    New user registrations for users who have uploaded at least one file.
    Grouped by registration date (UserAdditionalInfo.created).
    """
    window = get_window(request)
    period = get_period(request)

    # Users who have at least one ValidationRequest
    active_user_ids = (
        ValidationRequest.objects
        .values_list("created_by_id", flat=True)
        .distinct()
    )

    # Base queryset: registered users that are active (have uploads)
    base_qs = UserAdditionalInfo.objects.filter(user_id__in=active_user_ids)

    if period == "total":
        total = base_qs.count()

        return chart_response(
            title="Active user registrations (Total)",
            labels=["Total"],
            datasets=[{
                "label": "Active registrations",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [total],
            }],
        )

    users_qs = base_qs.filter(created__year=year)

    grouped = group_by_period(
        users_qs,
        period,
        "registrations",
        Count("id"),
        window=window,
    )

    regs_dict = fill_period_dict(
        grouped,
        period,
        year,
        key="registrations",
        transform=int,
        window=window,
    )

    return chart_response(
        title=f"Active user registrations in {year}",
        labels=list(regs_dict.keys()),
        datasets=[{
            "label": "Active registrations",
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
    window = get_window(request)

    if period == "total":
        qs = ValidationRequest.objects.all()
        total_uploaders = qs.values("created_by").distinct().count()
        vendor_uploaders = qs.filter(
            created_by__useradditionalinfo__is_vendor=True
        ).values("created_by").distinct().count()
        enduser_uploaders = total_uploaders - vendor_uploaders

        return chart_response(
            title="Uploaders (vendors vs end-users, Total)",
            labels=["End users", "Vendors"],
            datasets=[{
                "label": "Uploaders",
                "backgroundColor": [COLORS["primary"], COLORS["success"]],
                "borderColor": [COLORS["primary"], COLORS["success"]],
                "data": [enduser_uploaders, vendor_uploaders],
            }]
        )

    qs = ValidationRequest.objects.filter(created__year=year)

    total_qs = group_by_period(
        qs,
        period,
        "total",
        Count("created_by", distinct=True),
        window=window
    )

    vendor_qs = group_by_period(
        qs.filter(created_by__useradditionalinfo__is_vendor=True),
        period,
        "vendors",
        Count("created_by", distinct=True),
        window=window
    )

    total_dict = fill_period_dict(total_qs, period, year, key="total", transform=int, window=window)
    vendor_dict = fill_period_dict(vendor_qs, period, year, key="vendors", transform=int, window=window)

    enduser_dict = {lbl: total_dict[lbl] - vendor_dict.get(lbl, 0) for lbl in total_dict}
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
def get_usage_by_channel_chart(request, year):
    """
    Distinct channels per period, split into WebUI vs API.
    """
    period = get_period(request)
    window = get_window(request)

    if period == "total":
        qs = ValidationRequest.objects.all()
        total_uploaders = qs.values("channel").distinct().count()
        api_uploaders = qs.filter(
            channel=ValidationRequest.Channel.API
        ).values("id").distinct().count()
        webui_uploaders = total_uploaders - api_uploaders

        return chart_response(
            title="Channels (WebUI vs API, Total)",
            labels=["WebUI", "API"],
            datasets=[{
                "label": "Channels",
                "backgroundColor": [COLORS["primary"], COLORS["success"]],
                "borderColor": [COLORS["primary"], COLORS["success"]],
                "data": [webui_uploaders, api_uploaders],
            }]
        )

    qs = ValidationRequest.objects.filter(created__year=year)

    total_qs = group_by_period(
        qs,
        period,
        "total",
        Count("id", distinct=True),
        window=window
    )

    api_qs = group_by_period(
        qs.filter(channel=ValidationRequest.Channel.API),
        period,
        ValidationRequest.Channel.API,
        Count("id", distinct=True),
        window=window
    )

    total_dict = fill_period_dict(total_qs, period, year, key="total", transform=int, window=window)
    api_dict = fill_period_dict(api_qs, period, year, key="API", transform=int, window=window)
    webui_dict = {lbl: total_dict[lbl] - api_dict.get(lbl, 0) for lbl in total_dict}
    labels = list(total_dict.keys())

    return chart_response(
        title=f"Channels (WebUI vs API) in {year}",
        labels=labels,
        datasets=[
            {
                "label": "WebUI",
                "backgroundColor": COLORS["primary"],
                "borderColor": COLORS["primary"],
                "data": [webui_dict[lbl] for lbl in labels],
                "stack": "stack1",
            },
            {
                "label": "API",
                "backgroundColor": COLORS["success"],
                "borderColor": COLORS["success"],
                "data": [api_dict[lbl] for lbl in labels],
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
    window = get_window(request)

    if period == "total":
        qs = Model.objects.all()
        uploader_ids = qs.values_list("uploaded_by_id", flat=True).distinct()
        vendor_flags = _vendor_flag_map(uploader_ids)

        vendor_count = 0
        enduser_count = 0

        for uid in uploader_ids:
            if vendor_flags.get(uid):
                vendor_count += qs.filter(uploaded_by_id=uid).count()
            else:
                enduser_count += qs.filter(uploaded_by_id=uid).count()

        return chart_response(
            title="Model uploads (vendors vs end-users, Total)",
            labels=["End‑user models", "Vendor models"],
            datasets=[{
                "label": "Model uploads",
                "backgroundColor": [COLORS["primary"], COLORS["success"]],
                "borderColor": [COLORS["primary"], COLORS["success"]],
                "data": [enduser_count, vendor_count],
            }]
        )

    qs = Model.objects.filter(created__year=year).annotate(
        uploader_id=F("uploaded_by_id")
    )

    vendor_flags = _vendor_flag_map(
        qs.values_list("uploader_id", flat=True).distinct()
    )

    annotated_qs = PERIODS[period]["annotate"](qs)

    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated_qs = annotated_qs.filter(period__in=label_values)

    grouped = annotated_qs.values("period", "uploader_id")

    vendor_counts = dict_for_period(period, year, window=window)
    enduser_counts = dict_for_period(period, year, window=window)

    for row in grouped:
        uid = row["uploader_id"]
        period_label = PERIODS[period]["label"](row)

        if period_label not in vendor_counts:
            continue

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
    period = get_period(request)

    qs = Model.objects.filter(produced_by__isnull=False)
    if period != "total":
        qs = qs.filter(created__year=year)

    agg = (
        qs.values("produced_by")
          .annotate(total=Count("id"))
          .order_by("-total")[:10]
    )

    if not agg:
        title = f"No uploads in {year}" if period != "total" else "No uploads (Total)"
        return chart_response(title, [], [])

    tool_map = AuthoringTool.objects.in_bulk([row["produced_by"] for row in agg])
    labels = [tool_map[row["produced_by"]].full_name for row in agg]
    data   = [row["total"] for row in agg]

    title = f"Top 10 authoring tools in {year}" if period != "total" else "Top 10 authoring tools (Total)"
    return chart_response(
        title=title,
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
    Distinct authoring tools observed per ... (Model.produced_by).
    """
    window = get_window(request)
    period = get_period(request)

    models_qs = Model.objects.filter(produced_by__isnull=False)

    if period == "total":
        distinct_count = models_qs.values("produced_by").distinct().count()
        return chart_response(
            title="Distinct authoring tools observed (Total)",
            labels=["Total"],
            datasets=[{
                "label": "Tools",
                "backgroundColor": COLORS["info"],
                "borderColor": COLORS["info"],
                "data": [distinct_count],
            }],
        )

    models_qs = models_qs.filter(created__year=year)

    grouped = group_by_period(
        models_qs,
        period,
        "tools",
        Count("produced_by", distinct=True),
        window=window
    )

    tools_dict = fill_period_dict(
        grouped,
        period,
        year,
        key="tools",
        transform=int,
        window=window
    )

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
def get_top_tools_ifc2x3_chart(request, year):
    period = get_period(request)

    qs = Model.objects.filter(
        produced_by__isnull=False,
        schema__iexact="IFC2X3",
    )
    if period != "total":
        qs = qs.filter(created__year=year)

    return _top_tools_chart_response(
        qs,
        period,
        year,
        title_prefix="Top 10 authoring tools for IFC2X3",
    )


@staff_member_required
def get_top_tools_ifc4_chart(request, year):
    period = get_period(request)

    qs = Model.objects.filter(
        produced_by__isnull=False,
        schema__iexact="IFC4",
    )
    if period != "total":
        qs = qs.filter(created__year=year)

    return _top_tools_chart_response(
        qs,
        period,
        year,
        title_prefix="Top 10 authoring tools for IFC4",
    )


@staff_member_required
def get_top_tools_ifc4x3_chart(request, year):
    period = get_period(request)

    qs = Model.objects.filter(
        produced_by__isnull=False,
        schema__icontains="IFC4X3",
    )
    if period != "total":
        qs = qs.filter(created__year=year)

    return _top_tools_chart_response(
        qs,
        period,
        year,
        title_prefix="Top 10 authoring tools for IFC4X3",
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
    
    active_users_total = (
        UserAdditionalInfo.objects
        .filter(
            Exists(
                Model.objects.filter(
                    uploaded_by_id=OuterRef("user_id")
                )
            )
        )
        .count()
)

    return JsonResponse({
        "users": users_total,
        "active_users": active_users_total,
        "files": files_total,
        "tools": tools_total,
    })


@staff_member_required
def get_uploads_per_2h_chart(request, year):
    period = get_period(request)
    window = get_window(request)
    tz = ZoneInfo("Europe/Amsterdam")

    qs = Model.objects.all()
    if period != "total" and not window:
        qs = qs.filter(created__year=year)

    annotated = PERIODS[period]["annotate"](qs) if period != "total" else PERIODS["month"]["annotate"](qs)
    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated = annotated.filter(period__in=label_values)

    agg = (
        annotated.annotate(local_hour=ExtractHour(Trunc("created", "hour", tzinfo=tz)))
                 .annotate(block_num=F("local_hour") / 2)
                 .values("block_num")
                 .annotate(uploads=Count("id"))
                 .order_by("block_num")
    )

    labels = [f"{b*2:02d}:00–{(b*2+2)%24:02d}:00" for b in range(12)]
    counts = [0] * 12
    for row in agg:
        b = int(row["block_num"])
        if 0 <= b <= 11:
            counts[b] = row["uploads"] or 0

    return chart_response(
        title="Uploads per 2-hour block",
        labels=labels,
        datasets=[{
            "label": "Uploads",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": counts,
        }],
    )


@staff_member_required
def get_queue_p95_chart(request, year):
    period = get_period(request)
    window = get_window(request)
    tz = ZoneInfo("Europe/Amsterdam")

    qs = ValidationRequest.objects.filter(started__isnull=False)
    if period != "total" and not window:
        qs = qs.filter(created__year=year)

    annotated = PERIODS[period]["annotate"](qs) if period != "total" else PERIODS["month"]["annotate"](qs)

    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated = annotated.filter(period__in=label_values)

    annotated = annotated.annotate(
        local_hour=ExtractHour(Trunc("created", "hour", tzinfo=tz)),
        block_num=Cast(F("local_hour") / 2, IntegerField()),
    )

    rows = annotated.values_list("block_num", "created", "started")

    buckets = {b: [] for b in range(12)}
    for b, created, started in rows:
        if b is None:
            continue
        bi = int(b)
        if 0 <= bi <= 11 and created and started:
            delta = (started - created).total_seconds()
            if delta is not None and delta >= 0:
                buckets[bi].append(delta)

    def pct95(values: list[float]) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        k = 0.95 * (len(values) - 1)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return float(values[int(k)])
        return float(values[f] + (k - f) * (values[c] - values[f]))

    labels = [f"{b*2:02d}:00–{(b*2+2)%24:02d}:00" for b in range(12)]
    p95 = [round(pct95(buckets[b]), 1) for b in range(12)]

    return chart_response(
        title="Queue p95 per 2-hour block",
        labels=labels,
        datasets=[{
            "label": "p95 queue (s)",
            "type": "line",
            "backgroundColor": COLORS["info"],
            "borderColor": COLORS["info"],
            "data": p95,
        }],
    )


@staff_member_required
def get_stuck_per_day_chart(request, year):
    period = get_period(request)
    window = get_window(request)
    tz = ZoneInfo("Europe/Amsterdam")

    qs = ValidationRequest.objects.filter(started__isnull=False)
    if period != "total" and not window:
        qs = qs.filter(created__year=year)

    annotated = PERIODS[period]["annotate"](qs) if period != "total" else PERIODS["month"]["annotate"](qs)

    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated = annotated.filter(period__in=label_values)

    annotated = annotated.annotate(
        queue_d=ExpressionWrapper(F("started") - F("created"), output_field=DurationField()),
        local_day=Trunc("created", "day", tzinfo=tz),
    )

    stuck_qs = (
        annotated.filter(queue_d__gt=datetime.timedelta(hours=1))
                 .values("local_day")
                 .annotate(stuck=Count("id"))
                 .order_by("local_day")
    )

    labels = [row["local_day"].date().isoformat() for row in stuck_qs]
    data   = [row["stuck"] for row in stuck_qs]

    return chart_response(
        title="Requests with queue > 1h (per day)",
        labels=labels,
        datasets=[{
            "label": "Stuck (>1h) requests",
            "backgroundColor": COLORS["danger"],
            "borderColor": COLORS["danger"],
            "data": data,
        }],
    )


@staff_member_required
def get_uploads_per_weekday_chart(request, year):
    period = get_period(request)
    window = get_window(request)
    tz = ZoneInfo("Europe/Amsterdam")

    qs = Model.objects.all()
    if period != "total" and not window:
        qs = qs.filter(created__year=year)

    annotated = PERIODS[period]["annotate"](qs) if period != "total" else PERIODS["month"]["annotate"](qs)

    if window:
        valid_labels = set(_rolling_labels(period, window))
        label_values = [
            int(lbl[1:]) if period in ["week", "quarter"]
            else MONTHS.index(lbl) + 1 if period == "month"
            else lbl
            for lbl in valid_labels
        ]
        annotated = annotated.filter(period__in=label_values)

    annotated = annotated.annotate(
        local_day=Trunc("created", "day", tzinfo=tz),
        dow=ExtractWeekDay(F("local_day")),
    )

    agg = (
        annotated.values("dow")
        .annotate(uploads=Count("id"))
        .order_by("dow")
    )

    name_map = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
    items = []
    for row in agg:
        dow = int(row["dow"] or 0)
        sort_key = 7 if dow == 1 else dow - 1
        items.append((sort_key, name_map.get(dow, str(dow)), int(row["uploads"])))

    items.sort(key=lambda x: x[0])
    labels = [i[1] for i in items]
    data   = [i[2] for i in items]

    return chart_response(
        title="Uploads per weekday",
        labels=labels,
        datasets=[{
            "label": "Uploads",
            "backgroundColor": COLORS["primary"],
            "borderColor": COLORS["primary"],
            "data": data,
        }],
    )
