import gzip
import os
import tempfile
from types import SimpleNamespace

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from apps.ifc_validation_bff.step_lines import (
    add_step_lines,
    can_view_step_lines,
    resolve_step_lines,
)

# line 1 is the header comment, so declarations start at line 2
SPF = """/* header */
#1=IFCPERSON('a',$,$);
#2=IFCORGANIZATION('semi;colon inside a string',$);
#12=IFCWALL('short id');
#123=IFCSLAB('longer id that must not match #12');
#200=IFCPOLYLOOP((#1,
#2,
#12));
#201=IFCLABEL('last');
"""


def _write(content, directory, name='sample.ifc', gzipped=False):

    path = os.path.join(directory, name)
    if gzipped:
        with gzip.open(path, 'wb') as file:
            file.write(content.encode())
    else:
        with open(path, 'wb') as file:
            file.write(content.encode())
    return path


class ResolveStepLinesTestCase(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = _write(SPF, self.dir)

    def test_returns_line_number_and_source(self):

        found = resolve_step_lines(self.path, [1])

        self.assertEqual(found[1]['line'], 2)
        self.assertEqual(found[1]['source'], "#1=IFCPERSON('a',$,$);")

    def test_semicolon_inside_string_does_not_terminate(self):

        found = resolve_step_lines(self.path, [2])

        self.assertEqual(found[2]['line'], 3)
        self.assertEqual(found[2]['source'], "#2=IFCORGANIZATION('semi;colon inside a string',$);")

    def test_shorter_id_is_not_matched_by_longer_one(self):

        found = resolve_step_lines(self.path, [12, 123])

        self.assertEqual(found[12]['line'], 4)
        self.assertEqual(found[123]['line'], 5)
        self.assertTrue(found[12]['source'].startswith('#12=IFCWALL'))

    def test_multi_line_entity_keeps_its_first_line(self):

        found = resolve_step_lines(self.path, [200, 201])

        self.assertEqual(found[200]['line'], 6)
        self.assertIn('\n', found[200]['source'])
        # the entity spans three lines, so the next one must be counted correctly
        self.assertEqual(found[201]['line'], 9)

    def test_all_ids_are_resolved_in_a_single_pass(self):

        found = resolve_step_lines(self.path, [1, 2, 12, 123, 200, 201])

        self.assertEqual(len(found), 6)

    def test_unknown_id_is_absent_rather_than_an_error(self):

        self.assertEqual(resolve_step_lines(self.path, [999]), {})

    def test_no_ids_does_not_read_the_file(self):

        self.assertEqual(resolve_step_lines('/does/not/exist.ifc', []), {})

    def test_gzipped_file_yields_the_same_result(self):

        gz_path = _write(SPF, self.dir, name='sample2.ifc.gz', gzipped=True)

        self.assertEqual(resolve_step_lines(gz_path, [2, 200]),
                         resolve_step_lines(self.path, [2, 200]))


class AddStepLinesTestCase(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        _write(SPF, self.dir, name='uploaded.ifc')
        self.instances = {'i1': {'guid': '#1', 'type': 'IfcPerson'},
                          'i2': {'guid': '#12', 'type': 'IfcWall'}}

    def _request(self, file_name='uploaded.ifc'):
        return SimpleNamespace(id=1, file=file_name, model=SimpleNamespace(file=file_name))

    def test_adds_line_and_source_to_each_instance(self):

        with override_settings(MEDIA_ROOT=self.dir):
            add_step_lines(self.instances, self._request())

        self.assertEqual(self.instances['i1']['line'], 2)
        self.assertEqual(self.instances['i2']['line'], 4)
        self.assertTrue(self.instances['i1']['step_line'].startswith('#1=IFCPERSON'))

    def test_missing_file_leaves_instances_untouched(self):

        with override_settings(MEDIA_ROOT=self.dir):
            add_step_lines(self.instances, self._request(file_name='gone.ifc'))

        self.assertNotIn('step_line', self.instances['i1'])

    def test_gzipped_upload_is_found(self):

        _write(SPF, self.dir, name='archived.ifc.gz', gzipped=True)

        with override_settings(MEDIA_ROOT=self.dir):
            add_step_lines(self.instances, self._request(file_name='archived.ifc'))

        self.assertEqual(self.instances['i1']['line'], 2)

    def test_file_above_size_limit_is_skipped(self):

        with override_settings(MEDIA_ROOT=self.dir, STEP_LINE_MAX_FILE_SIZE_MB=0):
            add_step_lines(self.instances, self._request())

        self.assertNotIn('step_line', self.instances['i1'])

    def test_no_instances_is_a_no_op(self):

        empty = {}
        with override_settings(MEDIA_ROOT=self.dir):
            add_step_lines(empty, self._request())

        self.assertEqual(empty, {})


class CanViewStepLinesTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.group = Group.objects.create(name='step-line-viewers')
        cls.member = User.objects.create(username='member@test.org', is_active=True)
        cls.member.groups.add(cls.group)
        cls.staff = User.objects.create(username='staff@test.org', is_active=True, is_staff=True)
        cls.superuser = User.objects.create(username='super@test.org', is_active=True, is_superuser=True)
        cls.regular = User.objects.create(username='user@test.org', is_active=True)

    def test_group_member_may_view(self):
        self.assertTrue(can_view_step_lines(self.member))

    def test_superuser_alone_may_not_view(self):
        # no bypass: even a superuser has to be added to the group
        self.assertFalse(can_view_step_lines(self.superuser))

    def test_staff_alone_may_not_view(self):
        self.assertFalse(can_view_step_lines(self.staff))

    def test_regular_user_may_not_view(self):
        self.assertFalse(can_view_step_lines(self.regular))

    def test_no_user_may_not_view(self):
        self.assertFalse(can_view_step_lines(None))

    @override_settings(STEP_LINE_VIEWER_GROUP='another-group')
    def test_group_name_is_configurable(self):
        self.assertFalse(can_view_step_lines(self.member))
