import sys
import subprocess

from django.test import SimpleTestCase, TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import ValidationRequest, ValidationTask, set_user_context

from ..tasks.check_programs import run_subprocess_wait, run_subprocess


class SubprocessPeakRssTestCase(SimpleTestCase):

    def test_peak_rss_captured_for_memory_hungry_subprocess(self):
        # allocate ~100 MB and stay alive long enough for the 0.2s poll to sample it
        child = "data = bytearray(100 * 1024 * 1024)\nimport time\ntime.sleep(0.6)"
        proc = run_subprocess_wait(
            [sys.executable, "-c", child],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIsNotNone(proc.peak_rss_kb)
        self.assertGreater(proc.peak_rss_kb, 100 * 1024)
        self.assertIsNotNone(proc.min_mem_available_kb)
        self.assertGreater(proc.min_mem_available_kb, 0)

    def test_fast_subprocess_still_succeeds_without_peak_sample(self):
        # a subprocess that exits before the first 0.2s poll simply has no sample
        proc = run_subprocess_wait(
            [sys.executable, "-c", "print('hi')"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "hi")

    def test_peak_rss_includes_nested_child_processes(self):
        # gherkin spawns behave as a nested child, so grandchildren must be counted:
        # thin direct child, nested child allocates ~150 MB
        child = (
            "import subprocess, sys\n"
            "subprocess.run([sys.executable, '-c', "
            "'data = bytearray(150 * 1024 * 1024)\\nimport time\\ntime.sleep(0.8)'])\n"
        )
        proc = run_subprocess_wait(
            [sys.executable, "-c", child],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIsNotNone(proc.peak_rss_kb)
        self.assertGreater(proc.peak_rss_kb, 150 * 1024)

    def test_failing_subprocess_still_reports_returncode(self):
        proc = run_subprocess_wait(
            [sys.executable, "-c", "import sys; sys.exit(3)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.assertEqual(proc.returncode, 3)


class RunSubprocessTaskLoggingTestCase(TransactionTestCase):

    def test_peak_rss_is_logged_for_a_real_validation_task(self):
        user, _ = User.objects.get_or_create(id=1, defaults={'username': 'SYSTEM', 'is_active': True})
        set_user_context(user)
        request = ValidationRequest.objects.create(
            file_name='wall-with-opening-and-window.ifc',
            file='wall-with-opening-and-window.ifc',
            size=12789
        )
        task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.SYNTAX)

        child = "data = bytearray(50 * 1024 * 1024)\nimport time\ntime.sleep(0.5)"
        with self.assertLogs('ifc_validation', level='INFO') as captured:
            proc = run_subprocess(task, [sys.executable, "-c", child])

        self.assertEqual(proc.returncode, 0)
        peak_lines = [line for line in captured.output if 'Peak RSS for' in line]
        self.assertEqual(len(peak_lines), 1)
        self.assertIn(f'task #{task.id}', peak_lines[0])
        self.assertIn('min MemAvailable during run', peak_lines[0])
        self.assertIn('worker RSS', peak_lines[0])
