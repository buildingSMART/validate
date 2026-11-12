from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from pypdf import PdfReader
import pymupdf

from apps.ifc_validation_models.models import ValidationRequest, WhiteListEntry, WhiteListQueryFragment, set_user_context
from apps.ifc_validation_bff.report.pdf import artifact_path, generate_pdf, load_full_report, render_pdf, static_asset_uri
from apps.ifc_validation_bff.datamodel.load import load_dashboard, load_report
from apps.ifc_validation_bff.datamodel.ui import DashboardOptions
from .report_cases import CASES
from .report_factory import create_case


class ReportPDFTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create(username='pdf@test.org', email='pdf@test.org')
        cls.bob = User.objects.create(username='other-pdf@test.org', email='other-pdf@test.org')
        set_user_context(cls.alice)
        case = deepcopy(CASES[5])
        outcomes = [dict(feature='PDF001 - Mixed findings', severity=4 if i == 11 else 2,
                         observed={'value': 'Detailed IFC finding with a deliberately wrapped explanation. ' * 10},
                         expected={'value': f'requirement-{i}'}) for i in range(12)]
        outcomes.extend(dict(feature=f'PDF00{i} - Category {i}', severity=severity, expected='expected', observed='observed')
                        for i, severity in ((2, 2), (3, 0), (4, 3), (5, 1)))
        case['tasks'] = [dict(type='NORMATIVE_IA', outcomes=outcomes)]
        cls.item = create_case(case, cls.alice)
        cls.signature_item = create_case(CASES[7], cls.alice)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        config = override_settings(VALIDATION_REPORT_ROOT=self.directory.name)
        config.enable()
        self.addCleanup(config.disable)
        set_user_context(self.alice)

    def login_as(self, user):
        session = self.client.session
        session['user'] = {'email': user.email}
        session.save()

    def test_full_projection_orders_effective_severity_before_capping_and_reuses_templates(self):
        document = load_full_report(self.item)
        self.assertEqual([chapter.anchor for chapter in document.chapters],
                         ['findings', 'warnings', 'passed', 'not-applicable'])
        group = document.chapters[0].reports[0].section.items[0]
        self.assertEqual(group.results[0].severity_after_whitelisting, 4)
        self.assertEqual(len(group.results), 10)
        self.assertEqual(group.occurrence_count, 12)
        self.assertTrue(all(chapter.reports for chapter in document.chapters))
        html = render_to_string('report/page.html', {'pdf': True, 'document': document, 'report': document.file})
        for unexpected in ('<details', '<summary', '<textarea', 'hx-get=', '<script'):
            self.assertNotIn(unexpected, html)
        for text in ('Report overview', 'File metadata', 'Expected', 'Observed', 'Only the first 10', 'Validation execution'):
            self.assertIn(text, html)
        self.assertEqual(html.count('File Name in Header'), 1)
        self.assertEqual(document.conformance_status, 'n')  # absent checks cannot become green

    def test_real_pdf_has_bookmarks_page_numbers_repeated_headers_and_all_categories(self):
        document = load_full_report(self.item)
        payload = render_pdf(document)
        reader = PdfReader(BytesIO(payload))
        pdf = pymupdf.open(stream=payload, filetype='pdf')
        texts = [page.get_text() for page in pdf]
        text = '\n'.join(texts)
        self.assertGreaterEqual(len(texts), 5)
        self.assertIn('Report overview', texts[0])
        self.assertIn('Validation execution', texts[0])  # complete contents fit on page one
        for number, page in enumerate(texts, 1):
            self.assertIn(f'Page {number} of {len(texts)}', ' '.join(page.split()))
        body_headers = [page for page in texts[1:] if 'Expected' in page and 'Observed' in page]
        self.assertGreaterEqual(len(body_headers), 2)
        self.assertIn('requirement-11', text)
        self.assertIn('PDF003', text)
        self.assertIn('PDF005', text)
        def outline_titles(outline):
            for entry in outline:
                if isinstance(entry, list):
                    yield from outline_titles(entry)
                else:
                    yield entry.title
        titles = tuple(outline_titles(reader.outline))
        for title in ('Report overview', *(chapter.title for chapter in document.chapters), 'Validation execution'):
            self.assertIn(title, titles)
        self.assertEqual(reader.metadata.author, 'buildingSMART International')

    def test_overview_counts_rules_and_failure_occurrences_before_the_display_limit(self):
        task = self.item.tasks.get(type='NORMATIVE_IA')
        for feature, severity in (('PDF001 - Mixed findings', 1), ('PDF002 - Category 2', 1),
                                  ('PDF004 - Category 4', 2), ('PDF001 - Mixed findings', 3)):
            task.outcomes.create(feature=feature, severity_in_db=severity, outcome_code='X00040')
        document = load_full_report(self.item)
        row = next(row for row in document.overview if row.title == 'Normative IFC Rules')
        self.assertEqual((row.error_rules, row.error_outcomes), (1, 1))
        self.assertEqual((row.warning_rules, row.warning_outcomes), (2, 2))
        self.assertEqual(row.passed_rules, 2)  # one passed rule + one executed rule, without duplicates
        self.assertEqual(row.not_applicable_rules, 1)
        html = render_to_string('report/overview.html', {'document': document})
        self.assertInHTML('<th scope="colgroup" colspan="2">Errors</th>', html)
        self.assertInHTML('<th scope="colgroup" colspan="2">Warnings</th>', html)
        self.assertEqual(html.count('<th scope="col">Rules</th>'), 2)
        self.assertEqual(html.count('<th scope="col">Outcomes</th>'), 2)
        self.assertNotIn('<th>Executed</th>', html)

    def test_syntax_and_schema_passed_cells_show_validity_instead_of_rule_counts(self):
        document = load_full_report(self.item)
        for row in document.overview[:2]:
            for status in ('v', 'i', 'w', 'n', 'p', '-'):
                with self.subTest(layer=row.title, status=status):
                    single_row = replace(row, status=status, passed_rules=42)
                    html = render_to_string('report/overview.html', {'document': replace(document, overview=(single_row,))})
                    self.assertInHTML(f'<td>{"✓" if status == "v" else "✗"}</td>', html)
                    self.assertNotIn('<td>42</td>', html)

    def test_schema_cap_applies_before_overview_and_details_without_changing_database(self):
        case = deepcopy(CASES[0])
        case['tasks'] = [dict(type='SCHEMA', outcomes=[
            dict(feature='{"type": "schema", "attribute": "Name"}', severity=3 if i < 12 else 4,
                 observed=f'finding-{i}') for i in range(19)
        ] + [dict(feature='{"type": "schema", "attribute": "Description"}', severity=4,
                  observed='another group')])]
        request = create_case(case, self.alice)
        document = load_full_report(request)
        row = next(row for row in document.overview if row.title == 'IFC Schema')
        self.assertEqual((row.error_rules, row.error_outcomes), (2, 8))
        self.assertEqual((row.warning_rules, row.warning_outcomes), (1, 3))
        groups = document.chapters[0].reports[0].section.items
        group = next(group for group in groups if group.title == 'Schema - Name')
        self.assertEqual(group.occurrence_count, 10)
        self.assertEqual(len(group.results), 10)
        self.assertEqual(sum(result.severity_after_whitelisting == 4 for result in group.results), 7)
        self.assertEqual(request.tasks.get(type='SCHEMA').outcomes.count(), 20)

    def test_pdf_counts_successful_syntax_checks_without_changing_web_error_loading(self):
        case = deepcopy(CASES[0])
        case['model'].update(status_header_syntax='v', status_syntax='v')
        case['tasks'] = [dict(type=kind, outcomes=[dict(severity=2, outcome_code='P00010')])
                         for kind in ('HEADER_SYNTAX', 'SYNTAX')]
        request = create_case(case, self.alice)
        self.assertFalse(load_report(request, 'syntax').outcomes)
        document = load_full_report(request)
        row = next(row for row in document.overview if row.title == 'STEP Syntax')
        self.assertEqual(row.passed_rules, 2)
        self.assertEqual((row.error_rules, row.error_outcomes), (0, 0))

    def test_allowlisting_and_signatures_are_explicit_and_untruncated(self):
        entry = WhiteListEntry.objects.create(description='PDF known exception')
        WhiteListQueryFragment.objects.create(whitelist_entry=entry, column='feature', operation='EQUALS',
                                              right_hand_side='PDF001 - Mixed findings')
        document = load_full_report(self.item)
        self.assertFalse(document.chapters[0].reports)
        row = next(row for row in document.overview if row.title == 'Normative IFC Rules')
        self.assertEqual(row.passed_rules, 3)
        self.assertEqual(row.error_rules, 0)
        html = render_to_string('report/page.html', {'pdf': True, 'document': document, 'report': document.file})
        self.assertIn('Allowlisted · Passed (was Error)', html)
        signatures = load_full_report(self.signature_item)
        self.assertGreater(len(signatures.file.signatures[0].payload), 64)
        self.assertEqual(len(signatures.file.signatures), 2)
        rendered = pymupdf.open(stream=render_pdf(signatures), filetype='pdf')
        copied_text = ''.join(''.join(page.get_text() for page in rendered).split())
        self.assertIn(signatures.file.signatures[0].payload, copied_text)
        self.assertIn(signatures.file.signatures[0].fingerprint, copied_text)

    def test_artifacts_are_idempotent_and_downloads_enforce_ownership_state_and_deletion(self):
        with patch('apps.ifc_validation_bff.report.pdf.render_pdf', return_value=b'%PDF-example') as render:
            path = generate_pdf(self.item.pk)
            self.assertEqual(generate_pdf(self.item.pk), path)
            render.assert_called_once()
        self.login_as(self.alice)
        response = self.client.get(f'/v2/report_pdf/{self.item.public_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        response.close()
        dashboard = load_dashboard(self.alice, DashboardOptions(per_page=25))
        self.assertTrue(next(entry.pdf_ready for entry in dashboard.entries if entry.request_id == self.item.public_id))
        self.login_as(self.bob)
        self.assertEqual(self.client.get(f'/v2/report_pdf/{self.item.public_id}').status_code, 404)
        self.login_as(self.alice)
        self.item.mark_as_initiated()
        self.assertNotEqual(artifact_path(self.item), path)
        self.assertIsNone(generate_pdf(self.item.pk))
        self.assertEqual(self.client.get(f'/v2/report_pdf/{self.item.public_id}').status_code, 404)
        self.item.mark_as_completed()
        with patch('apps.ifc_validation_bff.report.pdf.render_pdf', return_value=b'%PDF-new'):
            new_path = generate_pdf(self.item.pk)
        self.client.post(f'/v2/delete/{self.item.public_id}', HTTP_HX_REQUEST='true')
        self.assertFalse(new_path.exists())
        self.assertFalse(path.exists())
        self.assertEqual(self.client.get(f'/v2/report_pdf/{self.item.public_id}').status_code, 404)

    def test_revalidation_during_render_is_not_published_and_assets_cannot_fetch_remote_urls(self):
        def rerun(document):
            self.item.mark_as_initiated()
            return b'%PDF-stale'
        with patch('apps.ifc_validation_bff.report.pdf.render_pdf', side_effect=rerun):
            self.assertIsNone(generate_pdf(self.item.pk))
        self.assertFalse(tuple(Path(self.directory.name).rglob('*.pdf')))
        for url in ('https://example.org/image.png', 'file:///etc/passwd', 'https://report.invalid/static/../secret'):
            with self.assertRaises(ValueError):
                static_asset_uri(url)

    @patch('apps.ifc_validation_models.decorators.set_django_system_user_context')
    def test_completion_queues_export_only_after_terminal_status(self, context):
        from apps.ifc_validation.tasks.task_runner import on_workflow_completed
        self.item.mark_as_initiated()
        def export(request_id):
            self.assertEqual(ValidationRequest.objects.get(pk=request_id).status, 'COMPLETED')
        with patch('apps.ifc_validation.tasks.task_runner.send_completion_email_task'), patch(
                'apps.ifc_validation.tasks.task_runner.generate_validation_report') as task:
            task.delay.side_effect = export
            on_workflow_completed.run(None, id=self.item.pk)
            task.delay.assert_called_once_with(request_id=self.item.pk)

    @patch('apps.ifc_validation_models.decorators.set_django_system_user_context')
    def test_render_errors_retry_independently_of_validation_status(self, context):
        from apps.ifc_validation.tasks.report_tasks import generate_validation_report
        failure = OSError('renderer unavailable')
        with patch('apps.ifc_validation_bff.report.pdf.generate_pdf', side_effect=failure), patch.object(
                generate_validation_report, 'retry', side_effect=RuntimeError('retry requested')) as retry:
            with self.assertRaisesRegex(RuntimeError, 'retry requested'):
                generate_validation_report.run(self.item.pk)
            retry.assert_called_once_with(exc=failure, countdown=30)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'COMPLETED')

    @patch('apps.ifc_validation_models.decorators.set_django_system_user_context')
    def test_time_limit_is_not_retried_and_lost_worker_is_not_redelivered(self, context):
        from celery.exceptions import SoftTimeLimitExceeded
        from apps.ifc_validation.tasks.report_tasks import generate_validation_report
        self.assertFalse(generate_validation_report.acks_late)
        with patch('apps.ifc_validation_bff.report.pdf.generate_pdf', side_effect=SoftTimeLimitExceeded()), patch.object(
                generate_validation_report, 'retry') as retry:
            self.assertIsNone(generate_validation_report.run(self.item.pk))
            retry.assert_not_called()
