from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.ifc_validation_models.models import ValidationRequest, set_user_context
from apps.ifc_validation_bff.datamodel.load import load_dashboard, load_model_summary, load_report
from apps.ifc_validation_bff.datamodel.model_summary import ModelSummary
from apps.ifc_validation_bff.datamodel.ui import DashboardOptions
from apps.ifc_validation_bff.report.pdf import load_full_report
from apps.ifc_validation_bff.views_legacy import format_request
from .report_cases import CASES
from .report_factory import create_case


class ModelSummaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(username="summary@test.org", email="summary@test.org")
        set_user_context(cls.user)
        cls.requests = [create_case(case, cls.user) for case in CASES]

    def assert_legacy_statuses(self, request, summary):
        legacy = format_request(request)
        for field, key in (
            ("header_status", "status_header"),
            ("signatures_status", "status_signatures"),
            ("security_status", "status_magic_clamav"),
            ("syntax_status", "status_syntax"),
            ("schema_status", "status_schema"),
            ("normative_status", "status_rules"),
            ("industry_status", "status_ind"),
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(summary, field), legacy[key])

    def test_fixture_metadata_and_statuses_preserve_existing_behavior(self):
        for request in self.requests:
            for state in ("PENDING", "INITIATED", "FAILED", "COMPLETED"):
                with self.subTest(request=request.file_name, state=state):
                    request.status = state
                    summary = load_model_summary(request)
                    self.assertIsInstance(summary, ModelSummary)
                    self.assertEqual(summary.request_id, request.public_id)
                    self.assertEqual(summary.created, request.created)
                    self.assertEqual(summary.file_name, request.file_name)
                    self.assertEqual(summary.size_bytes, request.size)
                    self.assertEqual(summary.progress, request.progress)
                    self.assertEqual(summary.header, request.model.header_validation or {})
                    self.assert_legacy_statuses(request, summary)

    def test_request_without_model_stays_pending(self):
        set_user_context(self.user)
        request = ValidationRequest.objects.create(file_name="pending.ifc", file="pending.ifc", size=1, progress=0)
        summary = load_model_summary(request)
        self.assertEqual(summary.header, {})
        self.assertEqual(summary.schema_status, "p")
        self.assertEqual(summary.normative_status, "p")
        self.assertEqual(summary.syntax_status, "p")
        self.assert_legacy_statuses(request, summary)

    def test_progress_100_does_not_hide_unfinished_checks(self):
        request = self.requests[0]
        request.status, request.progress = "INITIATED", 100
        request.model.status_prereq = "v"
        request.model.status_syntax = "v"
        request.model.status_header_syntax = "n"
        request.model._latest_task_status_by_type = {"SCHEMA": "n", "NORMATIVE_IA": "n", "NORMATIVE_IP": "v"}
        summary = load_model_summary(request)
        self.assertEqual(summary.schema_status, "p")
        self.assertEqual(summary.normative_status, "p")
        self.assertEqual(summary.syntax_status, "n")
        self.assert_legacy_statuses(request, summary)

        request.status = "COMPLETED"
        completed = load_model_summary(request)
        self.assertEqual(completed.schema_status, "n")
        self.assertEqual(completed.normative_status, "n")
        self.assertEqual(completed.syntax_status, "v")

    def test_sibling_errors_and_warnings_remain_visible(self):
        request = self.requests[0]
        request.status = "INITIATED"
        request.model.status_prereq = "i"
        request.model._latest_task_status_by_type = {"SCHEMA": "n", "NORMATIVE_IA": "n", "NORMATIVE_IP": "w"}
        summary = load_model_summary(request)
        self.assertEqual(summary.schema_status, "i")
        self.assertEqual(summary.normative_status, "w")
        self.assert_legacy_statuses(request, summary)

    def test_v2_consumers_do_not_call_legacy_projection(self):
        request = self.requests[5]
        with patch("apps.ifc_validation_bff.views_legacy.format_request", side_effect=AssertionError("v1 projection called")):
            summary = load_model_summary(request)
            report = load_report(request, "normative")
            dashboard = load_dashboard(self.user, DashboardOptions())
            document = load_full_report(request)
        self.assertEqual(report.status, summary.normative_status)
        self.assertTrue(dashboard.entries)
        self.assertEqual(document.signature_status, summary.signatures_status)
        with self.assertNumQueries(0):
            self.assertEqual(summary.file_name, request.file_name)
            self.assertIsInstance(summary.header, dict)
