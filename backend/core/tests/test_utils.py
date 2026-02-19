import tempfile

from django.test import TransactionTestCase

from ..utils import DeterministicAltNameStorage
from django.core.exceptions import SuspiciousFileOperation


class TestDeterministicAltNameStorage(TransactionTestCase):

    def test_generates_alternative_name(self):

        with tempfile.TemporaryDirectory() as tmpdir:

            # arrange
            storage = DeterministicAltNameStorage(location=tmpdir)
            
            # act
            name = storage.get_available_name('test.txt')
            print('Generated name: ', name)

            # assert
            assert name != 'test.txt'
            assert 'test_' in name
            assert '.txt' in name
            assert len(name.split('test_')[1].split('.txt')[0]) == 7

    def test_generates_unique_name_on_collision(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DeterministicAltNameStorage(location=tmpdir)
            name1 = storage.get_available_name('test.txt')
            print('Generated name1: ', name1)
            assert len(name1.split('test_')[1].split('.txt')[0]) == 7

            name2 = storage.get_available_name('test.txt')
            print('Generated name2: ', name2)
            assert name1 != name2
            assert len(name2.split('test_')[1].split('.txt')[0]) == 7

    def test_generates_alternative_name_path_traversal(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DeterministicAltNameStorage(location=tmpdir)
            with self.assertRaises(SuspiciousFileOperation):
                storage.get_available_name('../folder/test.txt')

    def test_generates_alternative_name_empty_name(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DeterministicAltNameStorage(location=tmpdir)
            with self.assertRaises(SuspiciousFileOperation):
                storage.get_available_name('')

    def test_generates_alternative_name_single_dot(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DeterministicAltNameStorage(location=tmpdir)
            with self.assertRaises(SuspiciousFileOperation):
                storage.get_available_name('.')

    def test_generates_alternative_name_double_dot(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DeterministicAltNameStorage(location=tmpdir)
            with self.assertRaises(SuspiciousFileOperation):
                storage.get_available_name('..')

    def test_generates_alternative_slash(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = DeterministicAltNameStorage(location=tmpdir)
            with self.assertRaises(SuspiciousFileOperation):
                storage.get_available_name('/')
