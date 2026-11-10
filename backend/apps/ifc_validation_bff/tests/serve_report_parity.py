"""Serve deterministic real Django reports to Playwright, using a temporary SQLite DB.

Run from backend: python -m apps.ifc_validation_bff.tests.serve_report_parity
No validator, Celery worker, development database or API token is used.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--manifest", default="../e2e/test-results/report-parity.json")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ifc-report-parity-") as directory:
        os.environ["REPORT_PARITY_DATABASE"] = str(Path(directory, "reports.sqlite3"))
        os.environ["REPORT_PARITY_MEDIA"] = directory
        os.environ["DJANGO_SETTINGS_MODULE"] = "apps.ifc_validation_bff.tests.report_parity_settings"
        import django
        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.contrib.auth.models import Group, User
        from django.contrib.sessions.backends.db import SessionStore
        from apps.ifc_validation_models.models import UserAdditionalInfo, ValidationTask, WhiteListEntry, WhiteListQueryFragment, set_user_context
        from .report_factory import create_case
        from .report_cases import CASES
        from unittest.mock import patch
        from apps.ifc_validation_bff import views_legacy
        views_legacy.DEVELOPMENT = views_legacy.PREVIEW = False  # anonymous browser tests must not auto-login

        call_command("migrate", run_syncdb=True, verbosity=0, interactive=False)
        users = [User.objects.create(username=f"{name}@test.org", email=f"{name}@test.org", first_name=name,
                                     last_name="Tester", is_active=True) for name in ("reader", "source-reader")]
        source_group = Group.objects.create(name="step-line-viewers")
        users[1].groups.add(source_group)
        cookies = []
        for user in users:
            set_user_context(user)
            UserAdditionalInfo.objects.create(user=user, is_vendor_self_declared=False)
            session = SessionStore()
            session["user"] = {"email": user.email}
            session.save()
            cookies.append({"name": settings.SESSION_COOKIE_NAME, "value": session.session_key,
                            "domain": "localhost", "path": "/"})

        set_user_context(users[0])
        reports = []
        for case in CASES:
            request = create_case(case, users[0])
            if case["kind"] == "schema":
                for task_type in ("SCHEMA", "PREREQ"):
                    ValidationTask.objects.get_or_create(request=request, type=task_type, defaults={"status": "SKIPPED"})
            # Both selected normative task types exist in actual pipeline requests.
            if case["kind"] == "normative":
                for task_type in ("NORMATIVE_IA", "NORMATIVE_IP"):
                    ValidationTask.objects.get_or_create(request=request, type=task_type, defaults={"status": "SKIPPED"})
            declarations = [f"#{i['stepfile_id']}={i['ifc_type'].upper()}($);" for i in case["instances"]]
            Path(directory, case["file_name"]).write_text("/* report parity source */\n" + "\n".join(declarations))
            reports.append({"name": case["name"], "kind": case["kind"], "id": request.public_id})

        # A separate request exercises actual pagination without expanding individual rules.
        from copy import deepcopy
        pagination_case = deepcopy(CASES[5])
        pagination_case["tasks"][0]["outcomes"] = [dict(feature=f"ZZZ{i:03} - Rule", severity=4,
                                                          expected="expected", observed={"value": i}) for i in range(23)]
        pagination = create_case(pagination_case, users[0])
        ValidationTask.objects.create(request=pagination, type="NORMATIVE_IP", status="SKIPPED")

        def rule_report(values):
            case = deepcopy(CASES[5])
            case["tasks"][0]["outcomes"] = [dict(feature=feature, severity=4, instance=22, expected=expected,
                                                  observed=observed) for feature, expected, observed in values]
            request = create_case(case, users[0])
            ValidationTask.objects.create(request=request, type="NORMATIVE_IP", status="SKIPPED")
            return {"kind": "normative", "id": request.public_id}

        allowlisted = rule_report([("ALW001 - Known exception", {"value": 0}, {"value": False})])
        entry = WhiteListEntry.objects.create(description="Browser parity known exception")
        WhiteListQueryFragment.objects.create(whitelist_entry=entry, column="feature", operation="EQUALS",
                                              right_hand_side="ALW001 - Known exception")
        rich_values = rule_report([
            ("VAL001 - Entity", {"entity": "IfcBeam(#22)"}, 1),
            ("VAL002 - GUID characters", {"invalid_guid_chars": "0-9", "expected_or_observed": "expected"},
             {"invalid_guid_chars": ["!", "?"], "expected_or_observed": "observed", "inst": "bad!?"}),
            ("VAL003 - GUID length", {"length": 22, "expected_or_observed": "expected"},
             {"length": 3, "expected_or_observed": "observed", "inst": "bad"}),
            ("VAL004 - Measurement", {"num_digits": 4, "context": "direction", "expected": 0.0001},
             {"num_digits": 4, "context": "position", "observed": [1, 2]}),
            ("VAL005 - Unknown shapes", {"unknown": "shape"}, [1, "two"]),
        ])

        # A real stored PDF exercises dashboard readiness and authenticated download.
        from apps.ifc_validation_bff.report.pdf import generate_pdf
        from apps.ifc_validation_models.models import ValidationRequest
        generate_pdf(ValidationRequest.to_private_id(rich_values['id']))

        from apps.ifc_validation_models.models import ValidationRequest
        for name, status, progress in (("dashboard-pending.ifc", "PENDING", 0), ("dashboard-running.ifc", "INITIATED", 35)):
            ValidationRequest.objects.create(file_name=name, file=name, size=10, status=status, progress=progress)

        account_cookies = {}
        for name, active, affiliation in (("declaration", True, None), ("inactive", False, False)):
            user = User.objects.create(username=f"{name}@test.org", email=f"{name}@test.org", first_name=name,
                                       last_name="Tester", is_active=active)
            set_user_context(user)
            UserAdditionalInfo.objects.create(user=user, is_vendor_self_declared=affiliation)
            session = SessionStore()
            session["user"] = {"email": user.email}
            session.save()
            account_cookies[name] = {"name": settings.SESSION_COOKIE_NAME, "value": session.session_key,
                                     "domain": "localhost", "path": "/"}

        # Source reader must have the same access as the owner without an ownership bypass.
        # Staff access is already a supported report policy; source access still needs its group.
        users[1].is_staff = True
        users[1].save()
        manifest = Path(args.manifest)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"reports": reports, "cookies": cookies, "pagination": pagination.public_id,
                                        "allowlisted": allowlisted, "rich_values": rich_values, "accounts": account_cookies}))
        print(f"Report parity fixtures ready at http://localhost:{args.port}/bff/", flush=True)
        with patch("apps.ifc_validation_bff.ui.actions.enqueue_validation"):
            call_command("runserver", f"0.0.0.0:{args.port}", use_reloader=False, verbosity=0)


if __name__ == "__main__":
    main()
