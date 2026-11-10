import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.template.loader import render_to_string
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.ifc_validation_models.models import ValidationOutcome, ValidationRequest, ValidationTask, WhiteListEntry, WhiteListQueryFragment, set_user_context
from apps.ifc_validation_bff.report.build import build_report
from apps.ifc_validation_bff.datamodel.report import OutcomeSeverity, ReportOptions, GherkinResult, SourceLocation
from apps.ifc_validation_bff.datamodel.load import load_report
from apps.ifc_validation_bff.report.value_formatting import interpret_rule_value
from .report_factory import create_case
from .report_cases import CASES


class ReportHTMLTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create(username="alice@test.org", email="alice@test.org", is_active=True)
        cls.bob = User.objects.create(username="bob@test.org", email="bob@test.org", is_active=True)
        cls.staff = User.objects.create(username="staff@test.org", email="staff@test.org", is_staff=True)
        set_user_context(cls.alice)
        cls.requests = [create_case(case, cls.alice) for case in CASES]

    def login_as(self, user):
        session = self.client.session
        session["user"] = {"email": user.email}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def get_report(self, index=0, query="", **headers):
        request = self.requests[index]
        segment = 'rules' if CASES[index]['kind'] == 'normative' else CASES[index]['kind']
        return self.client.get(f"/v2/report_{segment}/{request.public_id}?{query.lstrip('&')}", **headers)

    def test_all_mapping_cases_render_as_html(self):
        self.login_as(self.alice)
        for index, case in enumerate(CASES):
            with self.subTest(case=case["name"]):
                response = self.get_report(index, "&include_all=1")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, case["file_name"])
                self.assertContains(response, 'data-testid="report-content"')

    def test_projection_and_rendering_do_no_database_work(self):
        inputs = load_report(self.requests[5], "normative", self.alice)
        with self.assertNumQueries(0):
            data, pagination = inputs.outcomes_grouped().outcome_groups_paginated("normative", ReportOptions(include_all=True))
            report = build_report(data, "normative")
            page = pagination.with_report(report)
            html = render_to_string("report/page.html", {"report": page.report, "page": page})
        self.assertIn("SLIDING_TO_RIGHT", html)
        self.assertIsInstance(report.section.items[0].results[0], GherkinResult)

    def test_metadata_header_and_signatures_have_named_fields(self):
        report = build_report(load_report(self.requests[7], "file", self.alice), "file")
        self.assertEqual(report.metadata.file_name, CASES[7]["file_name"])
        self.assertEqual(report.signatures[0].rsa_key_size, 2048)
        self.assertEqual(len(report.signatures[0].payload), 64)
        report = build_report(load_report(self.requests[10], "file", self.alice), "file")
        self.assertEqual(report.header.company_name, "□")
        self.assertIn("company_name", report.header.invalid_fields)

    def test_original_and_effective_severity_are_explicit(self):
        set_user_context(self.alice)
        entry = WhiteListEntry.objects.create(description="Test known schema exception")
        WhiteListQueryFragment.objects.create(whitelist_entry=entry, column="instance__ifc_type",
                                              operation="EQUALS", right_hand_side="IfcPropertySingleValue")
        data = load_report(self.requests[3], "schema", self.alice)
        result = build_report(data, "schema").section.items[0].results[0]
        self.assertEqual(result.severity_in_db, OutcomeSeverity.ERROR)
        self.assertEqual(result.severity_after_whitelisting, OutcomeSeverity.PASSED)
        self.assertTrue(result.allowlisted)
        selected, pagination = data.outcomes_grouped().outcome_groups_paginated("schema", ReportOptions())
        self.assertFalse(build_report(selected, "schema", include_all=False).section.items)
        selected, pagination = data.outcomes_grouped().outcome_groups_paginated("schema", ReportOptions(include_all=True))
        report = build_report(selected, "schema")
        page = pagination.with_report(report)
        html = render_to_string("report/section.html", {"report": page.report, "page": page})
        self.assertIn("ⓘ Allowlisted", html)
        self.assertIn('data-severity-in-db="4"', html)
        self.assertIn('data-severity-after-whitelisting="2"', html)

    def test_filter_fragment_and_ten_result_limit(self):
        self.login_as(self.alice)
        response = self.get_report(11, HTTP_HX_REQUEST="true")
        self.assertNotContains(response, "<!doctype")
        self.assertContains(response, "Only the first 10 occurrences")
        self.assertEqual(response.context["page"].total, 1)
        group = response.context["report"].section.items[0]
        self.assertEqual(len(group.results), 10)
        self.assertEqual(group.occurrence_count, 19)
        self.assertEqual([result.instance.step_id for result in group.results], list(range(1, 11)))
        self.assertIn("HX-Request", response["Vary"])

    def test_group_pagination_not_outcome_pagination(self):
        task = self.requests[5].tasks.get(type="NORMATIVE_IA")
        for index in range(15):
            ValidationOutcome.objects.create(validation_task=task, severity_in_db=4, feature=f"ZZZ{index:03} - Rule", observed="bad")
        self.login_as(self.alice)
        first = self.get_report(5)
        second = self.get_report(5, "&page=2")
        self.assertEqual(len(first.context["report"].section.items), 10)
        self.assertEqual(second.context["page"].first, 11)
        self.assertEqual(first.context["page"].total, second.context["page"].total)
        self.assertEqual(self.get_report(5, "&page=invalid").status_code, 200)

    def test_flat_group_pagination_only_projects_the_selected_groups(self):
        data = load_report(self.requests[5], "normative", self.alice)
        source = data.outcomes[0]
        data = data.with_outcomes(
            replace(source, feature=f"GROUP{index:03}", observed=f"result-{index}-{copy}")
            for copy in range(2) for index in range(25)
        )
        selected, pagination = data.outcomes_grouped().outcome_groups_paginated("normative", ReportOptions(page=2))
        self.assertEqual((pagination.total, pagination.first, pagination.last), (25, 11, 20))
        self.assertEqual(len(selected.outcomes), 20)
        with patch('apps.ifc_validation_bff.report.build.interpret_rule_value', wraps=interpret_rule_value) as interpret:
            report = build_report(selected, "normative", include_all=False)
        self.assertEqual(interpret.call_count, 40)  # Expected and Observed for twenty selected outcomes.
        self.assertEqual([group.title for group in report.section.items], [f"GROUP{index:03}" for index in range(10, 20)])
        self.assertTrue(all(group.occurrence_count == 2 for group in report.section.items))

    def test_visibility_is_applied_before_the_outcome_cap(self):
        data = load_report(self.requests[5], "normative", self.alice)
        source = data.outcomes[0]
        data = data.with_outcomes(
            replace(source, feature="MIX001", severity_in_db=severity, allowlisted=False)
            for severity in [OutcomeSeverity.PASSED] * 12 + [OutcomeSeverity.ERROR]
        )
        selected, pagination = data.outcomes_grouped().outcome_groups_paginated("normative", ReportOptions())
        report = build_report(selected, "normative", include_all=False)
        self.assertEqual(pagination.total, 1)
        group = report.section.items[0]
        self.assertEqual(group.occurrence_count, 13)
        self.assertEqual([result.severity_after_whitelisting for result in group.results], [OutcomeSeverity.ERROR])

    def test_schema_grouping_uses_normalized_constraint_titles(self):
        data = load_report(self.requests[3], "schema", self.alice)
        source = data.outcomes[0]
        data = data.with_outcomes([
            replace(source, feature='{"type": "schema", "attribute": "Name"}'),
            replace(source, feature='{"type": "schema", "attribute": "Description"}'),
            replace(source, feature='{"attribute":"Name","type":"schema"}'),
        ])
        selected, pagination = data.outcomes_grouped().outcome_groups_paginated("schema", ReportOptions(page=2), page_size=1)
        self.assertEqual(pagination.total, 2)
        self.assertEqual(len(selected.outcomes), 2)
        self.assertEqual({outcome.group_title for outcome in selected.outcomes}, {"Schema - Name"})

    def test_syntax_pagination_selects_individual_diagnostics(self):
        data = load_report(self.requests[0], "syntax", self.alice)
        data = data.with_outcomes(replace(data.outcomes[0], observed=f"diagnosis-{index}\nsource\n^") for index in range(12))
        selected, pagination = data.outcomes_grouped().outcome_groups_paginated("syntax", ReportOptions(page=2))
        report = build_report(selected, "syntax")
        self.assertEqual((pagination.total, pagination.first, pagination.last), (12, 11, 12))
        self.assertEqual([error.diagnosis for error in report.section.items], ['diagnosis-10', 'diagnosis-11'])

    def test_latest_task_and_missing_tasks(self):
        request = self.requests[0]
        task = ValidationTask.objects.create(request=request, type="SYNTAX", status="COMPLETED")
        ValidationOutcome.objects.create(validation_task=task, severity_in_db=4, observed="new diagnostic\nsource\n^")
        report = build_report(load_report(request, "syntax", self.alice), "syntax")
        self.assertEqual(len(report.section.items), 1)
        self.assertEqual(report.section.items[0].diagnosis, "new diagnostic")
        self.assertFalse(build_report(load_report(request, "industry", self.alice), "industry").section.items)

    def test_loading_query_count_does_not_grow_with_findings(self):
        def query_count():
            request = ValidationRequest.objects.select_related("model", "created_by", "model__produced_by").get(pk=self.requests[5].pk)
            with CaptureQueriesContext(connection) as queries:
                data = load_report(request, "normative", self.alice)
            return len(queries), data

        before, _ = query_count()
        task = self.requests[5].tasks.get(type="NORMATIVE_IA")
        instance = task.outcomes.first().instance
        for index in range(20):
            ValidationOutcome.objects.create(validation_task=task, instance=instance, severity_in_db=4,
                                              feature=f"QRY{index:03} - Query count", observed="bad")
        after, data = query_count()
        self.assertEqual(after, before)
        self.assertEqual(len(data.outcomes), 23)

    def test_source_requires_group_membership_and_can_be_missing(self):
        request = self.requests[3]
        data = load_report(request, "schema", self.alice)
        self.assertTrue(all(o.instance.source is None for o in data.outcomes if o.instance))
        group, _ = Group.objects.get_or_create(name="step-line-viewers")
        self.alice.groups.add(group)
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            data = load_report(request, "schema", self.alice)
            self.assertTrue(all(o.instance.source is None for o in data.outcomes if o.instance))
            Path(directory, request.file_name).write_text("#1=IFCPERSON($);\n")
            data = load_report(request, "schema", self.alice)
            instance = next(o.instance for o in data.outcomes if o.instance)
            self.assertEqual(instance.source, SourceLocation(1, "#1=IFCPERSON($);"))
            self.assertTrue(build_report(data, "schema").section.items[0].show_source)

    def test_ownership_staff_deletion_and_methods(self):
        self.login_as(self.bob)
        self.assertEqual(self.get_report().status_code, 404)
        self.login_as(self.staff)
        self.assertEqual(self.get_report().status_code, 200)
        self.login_as(self.alice)
        request = self.requests[0]
        request.deleted = True
        request.save()
        self.assertEqual(self.get_report().status_code, 404)
        self.assertEqual(self.client.get("/v2/report_file/xyz").status_code, 404)
        self.assertEqual(self.client.get(f"/v2/report_bsdd/{request.public_id}").status_code, 404)
        self.assertEqual(self.client.post(f"/v2/report_file/{request.public_id}").status_code, 405)

    def test_template_escapes_file_and_outcome_content(self):
        self.login_as(self.alice)
        request = self.requests[0]
        request.file_name = '<script>alert("file")</script>.ifc'
        request.save()
        response = self.get_report()
        self.assertNotContains(response, '<script>alert("file")')
        self.assertContains(response, '&lt;script&gt;')
