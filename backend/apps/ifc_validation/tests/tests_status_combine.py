from django.test import SimpleTestCase

from apps.ifc_validation_bff.status import status_combine


class StatusCombineTests(SimpleTestCase):

    def test_both_valid_returns_valid(self):
        self.assertEqual(status_combine('v', 'v'), 'v')

    def test_pending_and_valid_returns_pending(self):
        # Regression: previously returned 'v', causing a green flash in the UI
        # while a slower sibling task was still running.
        self.assertEqual(status_combine('p', 'v'), 'p')

    def test_pending_and_invalid_returns_invalid(self):
        # A known failure surfaces immediately even if a sibling is still pending
        # (e.g. a skipped task that will never write its status field).
        self.assertEqual(status_combine('p', 'i'), 'i')

    def test_valid_and_invalid_returns_invalid(self):
        self.assertEqual(status_combine('v', 'i'), 'i')

    def test_both_pending_returns_pending(self):
        self.assertEqual(status_combine('p', 'p'), 'p')

    def test_allow_not_executed_filters_n_when_mixed(self):
        self.assertEqual(status_combine('n', 'v', allow_not_executed=True), 'v')

    def test_allow_not_executed_keeps_n_when_all_n(self):
        self.assertEqual(status_combine('n', 'n', allow_not_executed=True), 'n')

    def test_not_validated_outranks_valid_when_not_stripped(self):
        # without allow_not_executed, a pending/not-validated 'n' must beat a sibling 'v'
        # (n=3 > v=2 in "-pvnwi") so schema/rules never show green while a check is pending
        self.assertEqual(status_combine('n', 'v'), 'n')
        self.assertEqual(status_combine('v', 'n'), 'n')
