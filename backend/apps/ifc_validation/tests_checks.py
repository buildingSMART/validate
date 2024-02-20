import os
import sys
import subprocess
import json

from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings

from apps.ifc_validation_models.models import *
from apps.ifc_validation_models.decorators import requires_django_user_context

from .tasks import get_absolute_file_path

from .checks import check_gherkin
from .checks import check_bsdd

class ChecksTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):

        """
        Creates a SYSTEM user in the (in-memory) test database.
        Runs once for the whole test case.
        """

        user = User.objects.create(id=1, username='SYSTEM', is_active=True)
        user.save()

    @requires_django_user_context
    def test_check_bsdd_returns_json(self):

        # arrange
        file_name = 'valid_file.ifc'
        task_id = 0  # dummy
        file_path = get_absolute_file_path(file_name)

        # act
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_bsdd.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task_id)]
        proc = subprocess.run(
            check_program,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=os.environ.copy()
        )

        # assert
        self.assertEqual(0, proc.returncode)
        self.assertIsNotNone(proc.stdout)
        self.assertTrue(len(proc.stdout) != 0)
        self.assertTrue(proc.stderr is None or len(proc.stderr) == 0)
        results = json.loads(proc.stdout)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['domain_file'], 'no IfcClassification')
        
    @requires_django_user_context
    def test_check_bsdd_returns_json_2(self):

        # arrange
        file_name = 'MasterFormat2016Edition.ifc' # invalid class
        task_id = 0  # dummy
        file_path = get_absolute_file_path(file_name)

        # act
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_bsdd.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task_id)]
        proc = subprocess.run(
            check_program,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=os.environ.copy()
        )

        # assert
        self.assertEqual(0, proc.returncode)
        self.assertIsNotNone(proc.stdout)
        self.assertTrue(len(proc.stdout) != 0)
        self.assertTrue(proc.stderr is None or len(proc.stderr) == 0)
        results = json.loads(proc.stdout)
        self.assertEqual(len(results), 1)
    
    @requires_django_user_context
    def test_check_bsdd_returns_json_3(self):

        # arrange
        file_name = 'Molio_with_URIs.ifc'
        task_id = 0  # dummy
        file_path = get_absolute_file_path(file_name)

        # act
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_bsdd.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task_id)]
        proc = subprocess.run(
            check_program,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=os.environ.copy()
        )

        # assert
        self.assertEqual(0, proc.returncode)
        self.assertIsNotNone(proc.stdout)
        self.assertTrue(len(proc.stdout) != 0)
        self.assertTrue(proc.stderr is None or len(proc.stderr) == 0)
        results = json.loads(proc.stdout)
        self.assertTrue(len(results) > 10)
    