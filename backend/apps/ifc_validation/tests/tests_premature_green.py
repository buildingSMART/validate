"""No UI status cell may show GREEN ('v') before a contributing check has actually
passed — i.e. it must never be green *before it turns red*. This covers the
'skipped shows green' bug + the syntax in-progress flash. The assertions below replicate
the cell expressions in apps/ifc_validation_bff/views_legacy.py format_request() exactly;
keep them in sync with that file (status_schema / status_rules / status_syntax).

Execution order (apps/ifc_validation/tasks/configs.py + task_runner.py): serial
magic_clamav -> header_syntax -> header -> syntax -> prerequisites, then parallel
schema, signatures, IA, IP, industry. So earlier tasks finish while later siblings are
still pending = the window where a premature green could appear.
"""
from django.test import TestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import (
    Model, ValidationRequest, ValidationTask, ValidationOutcome, set_user_context,
)
from apps.ifc_validation_bff.status import status_combine

S = ValidationOutcome.OutcomeSeverity
T = ValidationTask.Type
St = Model.Status


# ---- exact replicas of the BFF cell assembly (views_legacy.py format_request) ----
def ui_schema(m):
    return status_combine(
        "p" if m.status_schema_calculated is None else m.status_schema_calculated,
        "p" if m.status_prereq is None else m.status_prereq)

def ui_rules(m):
    return status_combine(
        "p" if m.status_ia_calculated is None else m.status_ia_calculated,
        "p" if m.status_ip_calculated is None else m.status_ip_calculated)

def ui_syntax(m, completed):
    # allow_not_executed is gated on request COMPLETED (see views_legacy.py)
    return status_combine(
        "p" if m.status_syntax is None else m.status_syntax,
        "p" if m.status_header_syntax is None else m.status_header_syntax,
        allow_not_executed=completed)


class NoPrematureGreenTestCase(TestCase):

    @staticmethod
    def _user():
        u, _ = User.objects.get_or_create(id=1, defaults={'username': 'SYSTEM', 'is_active': True})
        set_user_context(u)
        return u

    def _model(self):
        u = self._user()
        m = Model.objects.create(file_name='m.ifc', size=1, uploaded_by=u)
        r = ValidationRequest.objects.create(file_name='m.ifc', file='m.ifc', size=1)
        r.model = m; r.save()
        self.req = r
        return m

    def _task(self, ttype, severities):
        t = ValidationTask.objects.create(request=self.req, type=ttype)
        for s in severities:
            ValidationOutcome.objects.create(validation_task=t, severity=s)
        return t

    def _fresh(self, m):
        return Model.objects.get(id=m.id)   # per-request fresh fetch (clears cached_property)

    # ===== SCHEMA — the original "green after IFC101" report =====
    def test_schema_inprogress_after_prereq_pass_is_not_green(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()        # IFC101/prereq passed
        self._task(T.SCHEMA, [])                     # schema task created, not yet run
        self.assertEqual(ui_schema(self._fresh(m)), St.NOT_VALIDATED)

    def test_schema_invalid_is_red(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [S.PASSED, S.ERROR])
        self.assertEqual(ui_schema(self._fresh(m)), St.INVALID)

    def test_schema_green_only_when_passed(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [S.PASSED])
        self.assertEqual(ui_schema(self._fresh(m)), St.VALID)

    # ===== RULES (IA + IP) =====
    def test_rules_inprogress_one_pending_is_not_green(self):
        m = self._model()
        self._task(T.NORMATIVE_IA, [S.PASSED])      # IA passed
        self._task(T.NORMATIVE_IP, [])              # IP still pending
        self.assertEqual(ui_rules(self._fresh(m)), St.NOT_VALIDATED)

    def test_rules_invalid_is_red(self):
        m = self._model()
        self._task(T.NORMATIVE_IA, [S.PASSED])
        self._task(T.NORMATIVE_IP, [S.PASSED, S.ERROR])
        self.assertEqual(ui_rules(self._fresh(m)), St.INVALID)

    def test_rules_green_only_when_both_pass(self):
        m = self._model()
        self._task(T.NORMATIVE_IA, [S.PASSED])
        self._task(T.NORMATIVE_IP, [S.PASSED])
        self.assertEqual(ui_rules(self._fresh(m)), St.VALID)

    # ===== RAW single-task cells: pending = default 'n' (grey), never green =====
    def test_raw_cells_default_not_validated_while_pending(self):
        m = self._model()
        for field in ['status_bsdd', 'status_header', 'status_industry_practices',
                      'status_signatures', 'status_magic_clamav', 'status_mvd', 'status_ids']:
            self.assertEqual(getattr(m, field), St.NOT_VALIDATED)

    # ===== SYNTAX — completed-gated allow_not_executed (fixes the in-progress flash) =====
    def test_syntax_inprogress_after_header_syntax_pass_is_not_green(self):
        # header_syntax finishes before syntax (serial); mid-run the strip is OFF so the
        # pending syntax 'n' is kept -> grey, not a premature green.
        m = self._model()
        m.status_header_syntax = St.VALID
        m.status_syntax = St.NOT_VALIDATED
        m.save()
        self.assertEqual(ui_syntax(m, completed=False), St.NOT_VALIDATED)

    def test_syntax_invalid_is_red(self):
        m = self._model()
        m.status_header_syntax = St.VALID
        m.status_syntax = St.INVALID
        m.save()
        self.assertEqual(ui_syntax(m, completed=False), St.INVALID)

    def test_syntax_legacy_completed_strips_not_executed_header_syntax(self):
        # legacy COMPLETED file: header_syntax never ran ('n'), syntax passed ('v') -> 'v'
        m = self._model()
        m.status_header_syntax = St.NOT_VALIDATED
        m.status_syntax = St.VALID
        m.save()
        self.assertEqual(ui_syntax(m, completed=True), St.VALID)

    def test_syntax_completed_all_skipped_stays_not_validated(self):
        m = self._model()
        m.status_header_syntax = St.NOT_VALIDATED
        m.status_syntax = St.NOT_VALIDATED
        m.save()
        self.assertEqual(ui_syntax(m, completed=True), St.NOT_VALIDATED)


# ---- gate-aware replicas of the FIXED BFF cells (views_legacy.py _pending_n_to_p) ----
# A not-yet-run check resolves to 'n' once the Model exists; while the request is NOT in a
# terminal state it must show the pending hourglass ('p'), not grey. Gate on request.status,
# NOT progress (progress hits 100 one task before status==COMPLETED — the t3' window).
VR = ValidationRequest.Status
_TERMINAL = (VR.COMPLETED, VR.FAILED)


def _gate(status, req_status):
    return 'p' if (status == St.NOT_VALIDATED and req_status not in _TERMINAL) else status


def ui_schema_cell(m, req_status):   # gate AFTER combine, so a real 'i'/'w' is never hidden
    return _gate(ui_schema(m), req_status)


def ui_rules_cell(m, req_status):
    return _gate(ui_rules(m), req_status)


def ui_header_cell(m, req_status):
    return _gate("p" if m.status_header is None else m.status_header, req_status)


class PendingNotValidatedGateTestCase(NoPrematureGreenTestCase):
    """IVS-820 follow-up: a not-yet-run check must show the pending hourglass ('p'),
    not grey 'n', until the *request* reaches a terminal state (COMPLETED/FAILED).
    Gates on request.status, NOT progress, because progress hits 100 one task before
    status flips to COMPLETED (the t3' window)."""

    # ----- SCHEMA cell -----
    def test_schema_inprogress_notrun_shows_hourglass(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [])
        self.assertEqual(ui_schema_cell(self._fresh(m), VR.INITIATED), 'p')

    def test_schema_t3prime_progress100_status_initiated_shows_hourglass(self):
        # t3': progress==100 but status still INITIATED -> must NOT flash grey
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [])
        self.req.progress = 100; self.req.status = VR.INITIATED; self.req.save()
        self.assertEqual(ui_schema_cell(self._fresh(m), VR.INITIATED), 'p')

    def test_schema_completed_skipped_stays_not_validated(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [])
        self.assertEqual(ui_schema_cell(self._fresh(m), VR.COMPLETED), St.NOT_VALIDATED)

    def test_schema_completed_passed_is_green(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [S.PASSED])
        self.assertEqual(ui_schema_cell(self._fresh(m), VR.COMPLETED), St.VALID)

    def test_schema_invalid_is_red_even_inprogress(self):
        m = self._model()
        m.status_prereq = St.VALID; m.save()
        self._task(T.SCHEMA, [S.PASSED, S.ERROR])
        self.assertEqual(ui_schema_cell(self._fresh(m), VR.INITIATED), St.INVALID)

    # ----- RULES cell: the warning-hiding regression guard -----
    def test_rules_inprogress_one_pending_shows_hourglass(self):
        m = self._model()
        self._task(T.NORMATIVE_IA, [S.PASSED])
        self._task(T.NORMATIVE_IP, [])
        self.assertEqual(ui_rules_cell(self._fresh(m), VR.INITIATED), 'p')

    def test_rules_warning_sibling_not_hidden_by_gate(self):
        # IA WARNING done, IP not run, mid-run: warning must STILL show ('w'), not be
        # swallowed into 'p'. This is why the gate is applied AFTER status_combine.
        m = self._model()
        self._task(T.NORMATIVE_IA, [S.PASSED, S.WARNING])
        self._task(T.NORMATIVE_IP, [])
        self.assertEqual(ui_rules_cell(self._fresh(m), VR.INITIATED), St.WARNING)

    def test_rules_completed_both_skipped_stays_not_validated(self):
        m = self._model()
        self._task(T.NORMATIVE_IA, [])
        self._task(T.NORMATIVE_IP, [])
        self.assertEqual(ui_rules_cell(self._fresh(m), VR.COMPLETED), St.NOT_VALIDATED)

    # ----- single-task raw cell (header) -----
    def test_header_inprogress_default_shows_hourglass(self):
        m = self._model()
        self.assertEqual(ui_header_cell(self._fresh(m), VR.INITIATED), 'p')

    def test_header_completed_default_stays_not_validated(self):
        m = self._model()
        self.assertEqual(ui_header_cell(self._fresh(m), VR.COMPLETED), St.NOT_VALIDATED)

    def test_header_failed_run_not_eternal_hourglass(self):
        # FAILED is terminal -> not-run cells settle to grey, never stuck on hourglass
        m = self._model()
        self.assertEqual(ui_header_cell(self._fresh(m), VR.FAILED), St.NOT_VALIDATED)
