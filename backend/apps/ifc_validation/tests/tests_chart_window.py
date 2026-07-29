"""
IVS-581 - aggregate charts must honour the rolling "Last N weeks" window.

Two layers:

1. WindowStartUnitTests  - pure date math: the new _window_start() cutoff must
   line up with the earliest bucket _rolling_labels() produces (the existing,
   trusted label logic the time-series charts use).

2. ChartWindowQueryTests - the *real* view functions run against a sqlite DB,
   proving the `created__date__gte=_window_start(...)` ORM filter actually
   executes (including the __date transform under USE_TZ) and narrows the data.
   Covers both query bases touched by the fix: ValidationRequest (processing
   status) and Model (top authoring tools).

`today` is frozen to 2026-06-28 (a Sunday) so the rolling window is deterministic
year-round.
"""
import datetime as dt
import json
import types
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.ifc_validation import chart_views
from apps.ifc_validation.chart_views import MONTHS, _rolling_labels, _window_start
from apps.ifc_validation_models.models import (
    AuthoringTool, Model, ValidationRequest, set_user_context,
)

FIXED_TODAY = dt.date(2026, 6, 28)  # a Sunday


class _FixedDate(dt.date):
    @classmethod
    def today(cls):
        return cls(FIXED_TODAY.year, FIXED_TODAY.month, FIXED_TODAY.day)


def _freeze_today():
    """Patch only chart_views' `datetime` name so today() is deterministic."""
    fake = types.SimpleNamespace(date=_FixedDate, timedelta=dt.timedelta, datetime=dt.datetime)
    return mock.patch.object(chart_views, "datetime", fake)


def _aware(d):
    return timezone.make_aware(dt.datetime(d.year, d.month, d.day, 12, 0))


class WindowStartUnitTests(TestCase):

    def test_cutoff_aligns_with_earliest_rolling_label(self):
        anchors = [dt.date(2026, 6, 28), dt.date(2026, 2, 3), dt.date(2026, 1, 1),
                   dt.date(2025, 12, 31), dt.date(2024, 3, 15)]
        for today in anchors:
            for period in ["day", "week", "month", "quarter"]:
                for window in [1, 2, 3, 4, 28, 52]:
                    start = _window_start(period, window, today)
                    earliest = _rolling_labels(period, window, today)[0]
                    msg = f"{period} w={window} today={today} start={start} earliest={earliest}"
                    if period == "day":
                        self.assertEqual(start.strftime("%Y-%m-%d"), earliest, msg)
                    elif period == "week":
                        self.assertEqual(f"W{start.isocalendar()[1]:02d}", earliest, msg)
                        self.assertEqual(start.weekday(), 0, msg)  # Monday
                    elif period == "month":
                        self.assertEqual(MONTHS[start.month - 1], earliest, msg)
                        self.assertEqual(start.day, 1, msg)
                    else:  # quarter
                        self.assertEqual(f"Q{(start.month - 1) // 3 + 1}", earliest, msg)
                        self.assertEqual(start.day, 1, msg)
                        self.assertIn(start.month, (1, 4, 7, 10), msg)

    def test_window_of_one_is_current_bucket(self):
        self.assertEqual(_window_start("day", 1, FIXED_TODAY), FIXED_TODAY)
        self.assertEqual(_window_start("week", 1, FIXED_TODAY), dt.date(2026, 6, 22))
        self.assertEqual(_window_start("month", 1, FIXED_TODAY), dt.date(2026, 6, 1))
        self.assertEqual(_window_start("quarter", 1, FIXED_TODAY), dt.date(2026, 4, 1))

    def test_window_crosses_year_boundary(self):
        # 28 weeks back from 2026-02-03 reaches into 2025
        self.assertEqual(_window_start("week", 28, dt.date(2026, 2, 3)).year, 2025)


class ChartWindowQueryTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()
        self.user = User.objects.create_user("staff", is_staff=True, is_active=True)
        set_user_context(self.user)  # required by the models' audit-trail save()

    def _set_created(self, obj, d):
        # `created` is auto_now_add; .update() issues raw SQL and bypasses it.
        type(obj).objects.filter(pk=obj.pk).update(created=_aware(d))

    def _call(self, view, period=None, window=None, year=2026):
        params = {}
        if period:
            params["period"] = period
        if window:
            params["window"] = str(window)
        req = self.rf.get("/api/charts/x/2026/", params)
        req.user = self.user
        with _freeze_today():
            resp = view(req, year)
        return json.loads(resp.content)["data"]

    # ------------------------------------------------------------------ #
    # ValidationRequest-based: get_processing_status_chart
    # ------------------------------------------------------------------ #
    def _seed_requests(self):
        rows = {
            "recent":   ("a.ifc", "COMPLETED", dt.date(2026, 6, 28)),  # in last 2 weeks
            "midweek":  ("b.ifc", "COMPLETED", dt.date(2026, 6, 20)),  # in last 2 weeks
            "early":    ("c.ifc", "FAILED",    dt.date(2026, 1, 10)),  # 2026, not last 2 wks
            "lastyear": ("d.ifc", "COMPLETED", dt.date(2025, 6, 28)),  # previous year
        }
        for name, status, d in rows.values():
            r = ValidationRequest.objects.create(file_name=name, file=name, size=1, status=status)
            self._set_created(r, d)

    def test_processing_status_no_window_is_full_year(self):
        self._seed_requests()
        data = self._call(chart_views.get_processing_status_chart, period="week")
        completed, failed = data["datasets"][0]["data"]
        self.assertEqual((completed, failed), (2, 1))  # lastyear excluded by year filter

    def test_processing_status_window_narrows_to_two_weeks(self):
        self._seed_requests()
        data = self._call(chart_views.get_processing_status_chart, period="week", window=2)
        completed, failed = data["datasets"][0]["data"]
        self.assertEqual((completed, failed), (2, 0))  # only recent + midweek survive

    def test_processing_status_total_ignores_window(self):
        self._seed_requests()
        data = self._call(chart_views.get_processing_status_chart, period="total", window=2)
        completed, failed = data["datasets"][0]["data"]
        self.assertEqual((completed, failed), (3, 1))  # all rows, all years

    # ------------------------------------------------------------------ #
    # Model-based: get_top_tools_ifc2x3_chart
    # ------------------------------------------------------------------ #
    def _seed_models(self):
        tool = AuthoringTool.objects.create(name="TestTool", version="1.0")
        for i, d in enumerate([dt.date(2026, 6, 28), dt.date(2026, 1, 10)]):
            m = Model.objects.create(
                file_name=f"m{i}.ifc", file=f"m{i}.ifc", size=1,
                schema="IFC2X3", produced_by=tool, uploaded_by=self.user,
            )
            self._set_created(m, d)
        return tool

    def test_top_tools_no_window_counts_full_year(self):
        self._seed_models()
        data = self._call(chart_views.get_top_tools_ifc2x3_chart, period="week")
        self.assertEqual(data["datasets"][0]["data"][0], 2)

    def test_top_tools_window_narrows_to_two_weeks(self):
        self._seed_models()
        data = self._call(chart_views.get_top_tools_ifc2x3_chart, period="week", window=2)
        self.assertEqual(data["datasets"][0]["data"][0], 1)
