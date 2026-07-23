import io
import json
import unittest
import zipfile

from django.test import TransactionTestCase
from django.contrib.auth.models import User

from apps.ifc_validation_models.models import *

try:
    import bcf  # noqa: F401
    HAS_BCF = True
except ImportError:
    HAS_BCF = False

WALL_GUID = '1kTvXnbbzCWw8lcMd1dR4o'
ALIGNMENT_GUID = '2O2Fr$t4X7Zf8NOew3FLKr'


@unittest.skipUnless(HAS_BCF, "bcf-client is not installed")
class BcfExportTestCase(TransactionTestCase):

    @staticmethod
    def set_user_context():
        user, _ = User.objects.get_or_create(id=1, defaults={'username': 'SYSTEM', 'is_active': True})
        set_user_context(user)
        return user

    def create_request_with_outcomes(self, user):

        # file name deliberately does not exist in MEDIA_ROOT; parent-element lookup is skipped
        request = ValidationRequest.objects.create(
            file_name='bcf_export_test.ifc',
            file='bcf_export_test.ifc',
            size=1024
        )
        model = Model.objects.create(file_name=request.file_name, file=request.file_name, size=1024, schema='IFC4', uploaded_by=user)
        request.model = model
        request.save()

        wall = ModelInstance.objects.create(
            model=model, stepfile_id=254, ifc_type='IfcWall',
            fields={'GlobalId': WALL_GUID, 'Name': 'Basic Wall:200mm'})
        alignment = ModelInstance.objects.create(
            model=model, stepfile_id=11, ifc_type='IfcAlignment',
            fields={'GlobalId': ALIGNMENT_GUID})
        point = ModelInstance.objects.create(
            model=model, stepfile_id=999, ifc_type='IfcCartesianPoint',
            fields={'Coordinates': [0.0, 0.0]})  # no GlobalId (non-rooted entity)

        task_schema = ValidationTask.objects.create(request=request, type=ValidationTask.Type.SCHEMA)
        task_normative = ValidationTask.objects.create(request=request, type=ValidationTask.Type.NORMATIVE_IA)
        task_syntax = ValidationTask.objects.create(request=request, type=ValidationTask.Type.SYNTAX)

        # more outcomes in a single group than MAX_OUTCOMES_PER_RULE (10)
        for sequence_number in range(14):
            ValidationOutcome.objects.create(
                validation_task=task_schema, instance=wall,
                feature=json.dumps({'attribute': 'IfcWall.Name', 'type': 'schema'}),
                outcome_code=ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR,
                severity=ValidationOutcome.OutcomeSeverity.ERROR,
                observed=f'Invalid value for Name attribute (occurrence {sequence_number + 1})')

        # entity without a GlobalId
        ValidationOutcome.objects.create(
            validation_task=task_schema, instance=point,
            feature=json.dumps({'attribute': 'IfcCartesianPoint.Coordinates', 'type': 'entity_rule'}),
            outcome_code=ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR,
            severity=ValidationOutcome.OutcomeSeverity.ERROR,
            observed='Coordinates dimensionality mismatch')

        # gherkin rule error with control characters in the message (must be sanitized)
        ValidationOutcome.objects.create(
            validation_task=task_normative, instance=alignment,
            feature='ALB002 - Alignment referents', feature_version=1,
            outcome_code=ValidationOutcome.ValidationOutcomeCode.VALUE_ERROR,
            severity=ValidationOutcome.OutcomeSeverity.ERROR,
            expected='IfcReferent nested in IfcAlignment',
            observed='No nested IfcReferent found \x00\x0b\x1f')

        # warning
        ValidationOutcome.objects.create(
            validation_task=task_normative, instance=wall,
            feature='SPS001 - Spatial containment', feature_version=1,
            outcome_code=ValidationOutcome.ValidationOutcomeCode.WARNING,
            severity=ValidationOutcome.OutcomeSeverity.WARNING,
            observed='Wall not contained in any storey')

        # passed outcome, must not become a topic
        ValidationOutcome.objects.create(
            validation_task=task_normative, instance=None,
            feature='GRF001 - Georeferencing', feature_version=1,
            outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
            severity=ValidationOutcome.OutcomeSeverity.PASSED)

        # syntax error without instance
        ValidationOutcome.objects.create(
            validation_task=task_syntax, instance=None,
            outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
            severity=ValidationOutcome.OutcomeSeverity.ERROR,
            observed='On line 42 column 7: unexpected token')

        return request

    def test_bcf_export_creates_expected_topics(self):

        user = BcfExportTestCase.set_user_context()
        request = self.create_request_with_outcomes(user)

        from apps.ifc_validation.bcf_export import generate_bcf_download
        content, stats = generate_bcf_download(request)

        # 10 capped wall errors + 1 point error + 1 gherkin error + 1 warning + 1 syntax error
        self.assertEqual(stats['topics'], 14)
        self.assertEqual(stats['with_viewpoint'], 12)  # not: point (no GlobalId), syntax (no instance)
        self.assertEqual(stats['truncated_groups'], 1)
        self.assertEqual(stats['skipped'], 4)

    def test_bcf_export_produces_valid_loadable_bcf(self):

        user = BcfExportTestCase.set_user_context()
        request = self.create_request_with_outcomes(user)

        from apps.ifc_validation.bcf_export import generate_bcf_download
        import tempfile, os
        from bcf.v2.bcfxml import BcfXml

        content, _ = generate_bcf_download(request)

        # well-formed zip with BCF 2.1 marker
        zip_file = zipfile.ZipFile(io.BytesIO(content))
        self.assertIn('bcf.version', zip_file.namelist())
        self.assertIn('VersionId="2.1"', zip_file.read('bcf.version').decode())

        # re-loadable by bcf-client (fails on unescaped control characters)
        with tempfile.TemporaryDirectory() as temp_dir:
            bcf_path = os.path.join(temp_dir, 'roundtrip.bcf')
            with open(bcf_path, 'wb') as file:
                file.write(content)
            with BcfXml.load(bcf_path) as bcfxml:
                topics = list(bcfxml.topics.values())
                self.assertEqual(len(topics), 14)
                titles = [handler.topic.title for handler in topics]
                self.assertTrue(any('ALB002' in title for title in titles))
                self.assertFalse(any('GRF001' in title for title in titles))  # passed is excluded

                # viewpoint selects the element by its IFC GlobalId
                alignment_handler = next(h for h in topics if 'ALB002' in h.topic.title)
                viewpoints = list(alignment_handler.viewpoints.values())
                self.assertEqual(len(viewpoints), 1)
                components = viewpoints[0].visualization_info.components.selection.component
                self.assertEqual(components[0].ifc_guid, ALIGNMENT_GUID)

    def test_bcf_export_without_error_outcomes_is_empty_but_valid(self):

        user = BcfExportTestCase.set_user_context()
        request = ValidationRequest.objects.create(file_name='bcf_export_empty.ifc', file='bcf_export_empty.ifc', size=100)
        task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.SCHEMA)
        ValidationOutcome.objects.create(
            validation_task=task, instance=None,
            outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
            severity=ValidationOutcome.OutcomeSeverity.PASSED)

        from apps.ifc_validation.bcf_export import generate_bcf_download
        content, stats = generate_bcf_download(request)

        self.assertEqual(stats['topics'], 0)
        zip_file = zipfile.ZipFile(io.BytesIO(content))
        self.assertIn('bcf.version', zip_file.namelist())
