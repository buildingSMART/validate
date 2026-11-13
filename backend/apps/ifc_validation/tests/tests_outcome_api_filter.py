from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.ifc_validation.api.v1.views import ValidationOutcomeListAPIView
from apps.ifc_validation_models.models import (
    ValidationOutcome,
    ValidationRequest,
    ValidationTask,
    set_user_context,
)


class ValidationOutcomeFilterTests(TestCase):
    """
    The list endpoint is always scoped to the caller (created_by), and the
    optional request_public_id / validation_task_public_id filters narrow
    within that scope. A malformed filter value must narrow to nothing, not
    silently fall back to returning every outcome the caller owns.
    """

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create(username="alice@test.org", email="alice@test.org", is_active=True)
        cls.bob = User.objects.create(username="bob@test.org", email="bob@test.org", is_active=True)

        set_user_context(cls.alice)
        cls.a1 = ValidationRequest.objects.create(file_name="a1.ifc", file="a1.ifc", size=1)
        cls.a2 = ValidationRequest.objects.create(file_name="a2.ifc", file="a2.ifc", size=1)
        t_a1 = ValidationTask.objects.create(request=cls.a1, type=ValidationTask.Type.SYNTAX)
        t_a2 = ValidationTask.objects.create(request=cls.a2, type=ValidationTask.Type.SYNTAX)
        cls.n_a1, cls.n_a2 = 3, 2
        for _ in range(cls.n_a1):
            ValidationOutcome.objects.create(validation_task=t_a1)
        for _ in range(cls.n_a2):
            ValidationOutcome.objects.create(validation_task=t_a2)

        set_user_context(cls.bob)
        cls.b1 = ValidationRequest.objects.create(file_name="b1.ifc", file="b1.ifc", size=1)
        t_b1 = ValidationTask.objects.create(request=cls.b1, type=ValidationTask.Type.SYNTAX)
        cls.n_b1 = 4
        for _ in range(cls.n_b1):
            ValidationOutcome.objects.create(validation_task=t_b1)

    def _queryset_for(self, user, **params):
        raw = APIRequestFactory().get("/api/v1/validationoutcome", params)
        drf_request = Request(raw)
        drf_request.user = user
        view = ValidationOutcomeListAPIView()
        view.request = drf_request
        return view.get_queryset()

    # --- scope is always enforced ---

    def test_no_filter_returns_only_own_outcomes(self):
        qs = self._queryset_for(self.alice)
        self.assertEqual(qs.count(), self.n_a1 + self.n_a2)

    def test_no_filter_never_returns_another_users_outcomes(self):
        qs = self._queryset_for(self.alice)
        self.assertFalse(qs.filter(validation_task__request=self.b1).exists())

    # --- valid filter narrows within own scope ---

    def test_valid_request_id_narrows_to_that_request(self):
        qs = self._queryset_for(self.alice, request_public_id=self.a1.public_id)
        self.assertEqual(qs.count(), self.n_a1)

    def test_valid_but_nonexistent_request_id_returns_nothing(self):
        qs = self._queryset_for(self.alice, request_public_id="r99999999")
        self.assertEqual(qs.count(), 0)

    # --- the fix: malformed value narrows to nothing, not "all my outcomes" ---

    def test_malformed_request_id_returns_nothing(self):
        qs = self._queryset_for(self.alice, request_public_id="notanid")
        self.assertEqual(qs.count(), 0)

    def test_malformed_request_id_does_not_leak_across_users(self):
        # Even if scope did not hold, a malformed value must not widen results.
        qs = self._queryset_for(self.alice, request_public_id="zzzmalformedzzz")
        self.assertEqual(qs.count(), 0)
        self.assertFalse(qs.filter(validation_task__request=self.b1).exists())

    def test_malformed_task_id_returns_nothing(self):
        qs = self._queryset_for(self.alice, validation_task_public_id="notatask")
        self.assertEqual(qs.count(), 0)

    def test_partially_valid_request_id_keeps_the_valid_part(self):
        qs = self._queryset_for(self.alice, request_public_id=f"{self.a1.public_id},garbage")
        self.assertEqual(qs.count(), self.n_a1)
