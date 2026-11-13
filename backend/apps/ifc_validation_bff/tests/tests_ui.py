import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import include, path

from apps.ifc_validation_models.models import UserAdditionalInfo, ValidationRequest, WhiteListEntry, WhiteListQueryFragment, set_user_context
from apps.ifc_validation_bff.datamodel.ui import Dashboard, DashboardOptions, Shell
from apps.ifc_validation_bff.datamodel.load import load_dashboard, load_shell
from apps.ifc_validation_bff.templatetags.ui_tags import dashboard_date
from .report_cases import CASES
from .report_factory import create_case


class FrontendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create(username="alice@test.org", email="alice@test.org", first_name="Alice", last_name="Tester")
        cls.bob = User.objects.create(username="bob@test.org", email="bob@test.org")
        cls.inactive = User.objects.create(username="inactive@test.org", email="inactive@test.org", is_active=False)
        for user in (cls.alice, cls.bob, cls.inactive):
            set_user_context(user)
            UserAdditionalInfo.objects.create(user=user, is_vendor_self_declared=False)
        set_user_context(cls.alice)
        cls.requests = [create_case(case, cls.alice) for case in CASES]
        cls.processing = ValidationRequest.objects.create(file_name="working.ifc", file="working.ifc", size=10,
                                                           status="INITIATED", progress=35)
        cls.pending = ValidationRequest.objects.create(file_name="pending.ifc", file="pending.ifc", size=10,
                                                        status="PENDING", progress=0)
        set_user_context(cls.bob)
        cls.bobs_request = ValidationRequest.objects.create(file_name="private.ifc", file="private.ifc", size=10)

    def login_as(self, user, client=None):
        client = client or self.client
        session = client.session
        session["user"] = {"email": user.email}
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_all_public_pages_and_protected_redirects(self):
        with patch("apps.ifc_validation_bff.ui.views.get_current_user", return_value=None):
            for path in ("/v2/", "/v2/scorecards", "/v2/waiting_zone", "/v2/logout"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                self.assertIsInstance(response.context["shell"], Shell)
            for path in ("/v2/dashboard", "/v2/allowlist"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/v2/login?next="))

    def test_dashboard_uses_owned_requests_and_typed_data(self):
        self.login_as(self.alice)
        response = self.client.get("/v2/dashboard?per_page=25")
        self.assertEqual(response.status_code, 200)
        data = response.context["dashboard"]
        self.assertIsInstance(data, Dashboard)
        self.assertEqual(data.total, 14)
        self.assertNotContains(response, "private.ifc")
        entries = {entry.request_id: entry for entry in data.entries}
        self.assertFalse(entries[self.processing.public_id].can_delete)
        self.assertTrue(entries[self.pending.public_id].can_delete)
        self.assertEqual(entries[self.pending.public_id].status, "PENDING")
        self.assertContains(response, "in queue")
        self.assertTrue(data.poll)
        self.assertContains(response, f'href="/v2/report_syntax/{self.requests[0].public_id}"')

    def test_templates_reverse_navigation_forms_and_reports_at_another_mount(self):
        request = self.client.get("/v2/waiting_zone").wsgi_request
        data = load_dashboard(self.alice, DashboardOptions(per_page=25))
        first = replace(data.entries[0], pdf_ready=True, signatures_status="v", header_errors=True)
        data = replace(data, entries=(first, *data.entries[1:]))
        shell = load_shell(request, self.alice, "Validation", "dashboard")
        urls = ModuleType("mounted_ui_urls")
        urls.urlpatterns = [path("validation/", include("apps.ifc_validation_bff.ui.urls"))]
        with override_settings(ROOT_URLCONF=urls), self.assertNumQueries(0):
            html = render_to_string("ui/dashboard.html", {"dashboard": data, "shell": shell})
        for fragment in (
            'href="/validation/"', 'href="/validation/dashboard"',
            'action="/validation/logout"', 'action="/validation/delete"',
            'action="/validation/upload"', 'hx-get="/validation/dashboard',
            f'hx-post="/validation/delete/{first.request_id}"',
            f'href="/validation/report_file/{first.request_id}#signatures"',
            f'href="/validation/report_pdf/{first.request_id}"',
        ):
            self.assertIn(fragment, html)
        self.assertNotIn('/v2/', html)

    def test_dashboard_template_does_not_query_models(self):
        request = self.client.get("/v2/waiting_zone").wsgi_request
        data = load_dashboard(self.alice, DashboardOptions(per_page=25))
        shell = load_shell(request, self.alice, "Validation", "dashboard")
        with self.assertNumQueries(0):
            render_to_string("ui/dashboard_panel.html", {"dashboard": data, "shell": shell})

    def test_paging_filter_and_poll_fragment(self):
        self.login_as(self.alice)
        response = self.client.get("/v2/dashboard?page=2&per_page=5", HTTP_HX_REQUEST="true")
        self.assertNotContains(response, "<!doctype")
        self.assertContains(response, 'id="dashboard-panel"')
        self.assertEqual(response.context["dashboard"].first, 6)
        self.assertEqual(len(response.context["dashboard"].entries), 5)
        response = self.client.get("/v2/dashboard?page=bad&per_page=999")
        self.assertEqual(response.context["dashboard"].options.per_page, 5)
        self.assertEqual(response.context["dashboard"].options.page, 1)

    def test_upload_validates_entire_batch_before_saving(self):
        self.login_as(self.alice)
        original = ValidationRequest.objects.count()
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory), patch("apps.ifc_validation_bff.ui.actions.enqueue_validation") as enqueue:
            bad = self.client.post("/v2/upload", {"file": [SimpleUploadedFile("ok.ifc", b"IFC"), SimpleUploadedFile("bad.exe", b"bad")]}, HTTP_HX_REQUEST="true")
            self.assertEqual(bad.status_code, 422)
            self.assertContains(bad, "only .ifc files", status_code=422)
            self.assertEqual(ValidationRequest.objects.count(), original)
            enqueue.assert_not_called()
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post("/v2/upload", {"file": [SimpleUploadedFile("first.ifc", b"IFC"), SimpleUploadedFile("second.ifc", b"IFC")]}, HTTP_HX_REQUEST="true")
            self.assertEqual(response["HX-Redirect"], "/v2/dashboard")
            self.assertEqual(enqueue.call_count, 2)
            self.assertEqual(ValidationRequest.objects.count(), original + 2)
            created = ValidationRequest.objects.get(file_name="first.ifc")
            self.assertEqual(created.created_by, self.alice)
            self.assertEqual(created.channel, "WEBUI")

    @override_settings(MAX_FILE_SIZE_IN_MB=0, MAX_FILES_PER_UPLOAD=1)
    def test_upload_limits_are_enforced_on_server(self):
        self.login_as(self.alice)
        response = self.client.post("/v2/upload", {"file": [SimpleUploadedFile("a.ifc", b"a"), SimpleUploadedFile("b.ifc", b"b")]})
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Upload at most 1 files", status_code=422)
        self.assertContains(response, "size limit", status_code=422)

    def test_deletion_is_owned_atomic_and_rejects_running_files(self):
        self.login_as(self.alice)
        for ids in ([self.bobs_request.public_id], [self.pending.public_id, self.processing.public_id], ["garbage"]):
            response = self.client.post("/v2/delete", {"selected": ids}, HTTP_HX_REQUEST="true")
            self.assertContains(response, 'role="alert"')
            self.pending.refresh_from_db()
            self.bobs_request.refresh_from_db()
            self.assertFalse(self.pending.deleted)
            self.assertFalse(self.bobs_request.deleted)
        response = self.client.post(f"/v2/delete/{self.pending.public_id}", {"selected": [self.requests[0].public_id]}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.pending.refresh_from_db()
        self.requests[0].refresh_from_db()
        self.assertTrue(self.pending.deleted)
        self.assertFalse(self.requests[0].deleted)  # clicking one row never deletes selected siblings

    def test_declaration_and_logout(self):
        self.login_as(self.alice)
        info = self.alice.useradditionalinfo
        info.is_vendor_self_declared = None
        info.save()
        self.assertContains(self.client.get("/v2/dashboard"), 'id="affiliation-dialog"')
        self.assertEqual(self.client.post("/v2/affiliation", {"is_vendor_self_declared": "invalid"}).status_code, 422)
        self.client.post("/v2/affiliation", {"is_vendor_self_declared": "false"}, HTTP_HX_REQUEST="true")
        info.refresh_from_db()
        self.assertIs(info.is_vendor_self_declared, False)
        self.assertNotContains(self.client.get("/v2/dashboard"), 'id="affiliation-dialog"')
        self.assertEqual(self.client.post("/v2/logout").url, "/v2/")
        self.assertNotIn("user", self.client.session)

    def test_inactive_user_cannot_use_dashboard_or_mutations(self):
        self.login_as(self.inactive)
        for method, path in (("get", "/v2/dashboard"), ("get", "/v2/allowlist"), ("post", "/v2/upload"), ("post", "/v2/delete")):
            response = getattr(self.client, method)(path)
            self.assertEqual(response.url, "/v2/waiting_zone")

    def test_allowlist_dataclasses_and_escaping(self):
        self.login_as(self.alice)
        set_user_context(self.alice)
        entry = WhiteListEntry.objects.create(description="<script>bad</script>")
        WhiteListQueryFragment.objects.create(whitelist_entry=entry, column="instance__ifc_type", operation="EQUALS", right_hand_side="IfcWall")
        response = self.client.get("/v2/allowlist")
        pattern = next(item for item in response.context["allowlist"].entries if item.id == entry.id).patterns[0]
        self.assertEqual(pattern.field, "type")
        self.assertEqual(pattern.value, "IfcWall")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>bad")

    def test_legacy_report_redirects(self):
        self.login_as(self.alice)
        item = self.requests[0]
        response = self.client.get(f"/report/{item.public_id}?type=syntax&include_all=1")
        self.assertEqual(response.url, f"/v2/report_syntax/{item.public_id}?include_all=1")

    def test_oauth_login_retains_only_v2_return_paths(self):
        with patch("core.views_auth.login", return_value=HttpResponseRedirect("https://identity.test/authorize")):
            response = self.client.get("/v2/login?next=/v2/allowlist")
            self.assertEqual(response.url, "https://identity.test/authorize")
            self.assertEqual(self.client.session["ui_return_to"], "/v2/allowlist")
            self.client.get("/v2/login?next=https://external.test/")
            self.assertEqual(self.client.session["ui_return_to"], "/v2/dashboard")

    def test_oauth_callback_returns_to_v2(self):
        session = self.client.session
        session['ui_return_to'] = '/v2/allowlist'
        session.save()
        with patch('core.views_auth.oauth.b2c.authorize_access_token', return_value={'userinfo': {
            'email': self.alice.email, 'given_name': 'Alice', 'family_name': 'Tester',
        }}):
            response = self.client.get('/v2/callback?code=test')
        self.assertEqual(response.url, '/v2/allowlist')
        self.assertNotIn('ui_return_to', self.client.session)

    def test_oauth_callback_sends_inactive_user_to_v2_waiting_zone(self):
        with patch('core.views_auth.oauth.b2c.authorize_access_token', return_value={'userinfo': {
            'email': self.inactive.email, 'given_name': 'Inactive', 'family_name': 'Tester',
        }}):
            response = self.client.get('/v2/callback?code=test')
        self.assertEqual(response.url, '/v2/waiting_zone')

    def test_unknown_v2_page_keeps_the_app_shell(self):
        self.login_as(self.alice)
        response = self.client.get('/v2/unknown-page')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Not Found', status_code=404)
        self.assertContains(response, '/v2/dashboard', status_code=404)

    @override_settings(MIDDLEWARE=["django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.csrf.CsrfViewMiddleware"])
    def test_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.login_as(self.alice, client)
        for path in ("/v2/upload", "/v2/delete", "/v2/affiliation", "/v2/logout"):
            self.assertEqual(client.post(path).status_code, 403)


class DashboardPresentationTests(SimpleTestCase):
    def test_checks_link_only_to_available_reports(self):
        for status in ('v', 'i', 'w', 'p', 'n', '-'):
            with self.subTest(status=status):
                html = render_to_string('ui/check.html', {
                    'status': status, 'label': 'STEP Syntax',
                    'report_route': 'ui:report-syntax', 'request_id': 'r123',
                })
                self.assertIn(f'data-status="{status}"', html)
                if status in ('v', 'i', 'w'):
                    self.assertIn('href="/v2/report_syntax/r123"', html)
                    self.assertIn('aria-label="STEP Syntax:', html)
                else:
                    self.assertNotIn('<a', html)

    def test_progress_labels_prioritize_request_state_over_percentage(self):
        created = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        for state, progress, label, element in (
            ('PENDING', 100, 'in queue', None),
            ('FAILED', 100, 'an error occured', None),
            ('INITIATED', None, '0%', '<progress'),
            ('INITIATED', 42, '42%', '<progress'),
            ('COMPLETED', 100, '2026-11-01 12:00:00', '<time'),
        ):
            with self.subTest(state=state, progress=progress):
                item = SimpleNamespace(status=state, progress=progress, created=created, file_name='test.ifc')
                with patch('apps.ifc_validation_bff.templatetags.ui_tags.timezone.now',
                           return_value=created + timedelta(days=10)):
                    html = render_to_string('ui/progress.html', {'entry': item})
                self.assertIn(label, html)
                if element:
                    self.assertIn(element, html)
                else:
                    self.assertNotIn('<time', html)
                    self.assertNotIn('<progress', html)
                if state == 'COMPLETED':
                    self.assertIn('title="2026-11-01 12:00:00 UTC"', html)

    def test_relative_date_format_and_cutoff_are_preserved(self):
        now = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        for elapsed, expected in (
            (timedelta(seconds=2), '2 seconds ago'),
            (timedelta(seconds=90), '1 minute ago'),
            (timedelta(hours=3), '3 hours ago'),
            (timedelta(days=2), '2 days ago'),
            (timedelta(days=8), '1 week ago'),
            (timedelta(days=8, seconds=1), '2026-11-02 11:59:59'),
        ):
            with self.subTest(elapsed=elapsed):
                self.assertEqual(dashboard_date(now - elapsed, now), expected)
