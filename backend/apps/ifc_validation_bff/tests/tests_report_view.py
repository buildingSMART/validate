from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase

from apps.ifc_validation_models.models import (
    Model,
    ValidationRequest,
    set_user_context,
)


class ReportViewTestCase(TestCase):
    """
    Tests for the BFF report endpoint (/api/report/<id>).

    Covers resolution by public request id ('r...') and public model id ('m...'),
    rejection of malformed ids, and the ownership / staff / soft-delete rules.
    """

    @classmethod
    def setUpTestData(cls):

        cls.alice = User.objects.create(username='alice@test.org', email='alice@test.org', is_active=True)
        cls.bob = User.objects.create(username='bob@test.org', email='bob@test.org', is_active=True)
        cls.staff = User.objects.create(username='staff@test.org', email='staff@test.org', is_active=True, is_staff=True)

        # request + linked model owned by alice
        set_user_context(cls.alice)
        cls.alice_model = Model.objects.create(file_name='alice.ifc', file='alice.ifc', size=1024, uploaded_by=cls.alice)
        cls.alice_request = ValidationRequest.objects.create(file_name='alice.ifc', file='alice.ifc', size=1024, model=cls.alice_model)

        # soft-deleted request owned by alice
        cls.alice_deleted_request = ValidationRequest.objects.create(file_name='deleted.ifc', file='deleted.ifc', size=1024, deleted=True)

        # request + linked model owned by bob
        set_user_context(cls.bob)
        cls.bob_model = Model.objects.create(file_name='bob.ifc', file='bob.ifc', size=1024, uploaded_by=cls.bob)
        cls.bob_request = ValidationRequest.objects.create(file_name='bob.ifc', file='bob.ifc', size=1024, model=cls.bob_model)

        # model without any validation request
        cls.orphan_model = Model.objects.create(file_name='orphan.ifc', file='orphan.ifc', size=1024, uploaded_by=cls.alice)

    def login_as(self, user):
        session = self.client.session
        session['user'] = {'email': user.email}
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def get_report(self, public_id):
        return self.client.get(f'/api/report/{public_id}')

    # --- happy paths ---

    def test_own_report_by_request_id_returns_200(self):

        self.login_as(self.alice)
        response = self.get_report(self.alice_request.public_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model']['id'], self.alice_request.public_id)

    def test_own_report_2nd_user_by_request_id_returns_200(self):
    
        self.login_as(self.bob)
        response = self.get_report(self.bob_request.public_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model']['id'], self.bob_request.public_id)

    def test_own_report_by_model_id_returns_200(self):

        self.login_as(self.alice)
        response = self.get_report(self.alice_model.public_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model']['id'], self.alice_request.public_id)

    def test_own_report_by_model_id_returns_200(self):
    
        self.login_as(self.bob)
        response = self.get_report(self.bob_model.public_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model']['id'], self.bob_request.public_id)

    # --- malformed / unknown ids (regression tests for 500s) ---

    def test_unknown_prefix_returns_404(self):

        self.login_as(self.alice)
        for public_id in ['t42', 'o42', 'u42']:
            with self.subTest(public_id=public_id):
                self.assertEqual(self.get_report(public_id).status_code, 404)

    def test_garbage_id_returns_404(self):

        self.login_as(self.alice)
        for public_id in ['hello', 'rfoo', 'r', 'm', 'm12x']:
            with self.subTest(public_id=public_id):
                self.assertEqual(self.get_report(public_id).status_code, 404)

    def test_model_id_without_request_returns_404(self):

        self.login_as(self.alice)
        self.assertEqual(self.get_report(self.orphan_model.public_id).status_code, 404)

    # --- ownership / staff / soft-delete rules ---

    def test_other_users_report_returns_404(self):

        self.login_as(self.bob)
        self.assertEqual(self.get_report(self.alice_request.public_id).status_code, 404)
        self.assertEqual(self.get_report(self.alice_model.public_id).status_code, 404)

    def test_own_deleted_report_returns_404(self):

        self.login_as(self.alice)
        self.assertEqual(self.get_report(self.alice_deleted_request.public_id).status_code, 404)

    def test_staff_can_view_other_users_report(self):

        self.login_as(self.staff)
        response = self.get_report(self.alice_request.public_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model']['id'], self.alice_request.public_id)

    def test_staff_can_view_deleted_report(self):

        self.login_as(self.staff)
        self.assertEqual(self.get_report(self.alice_deleted_request.public_id).status_code, 200)

    # --- authentication ---

    # RW: this test fails because there is a fallback for development user in DEV
    # def test_unauthenticated_returns_login_redirect(self):
    #
    #     response = self.get_report(self.alice_request.public_id)
    #
    #     self.assertEqual(response.status_code, 200)
    #     self.assertIn('redirect', response.json())
