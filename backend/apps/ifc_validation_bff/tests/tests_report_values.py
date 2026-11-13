from dataclasses import replace

from django.test import SimpleTestCase

from apps.ifc_validation_bff.datamodel.report import AllowedValues, AttributeValue, EntityReference, Outcome, OutcomeSeverity, UnrecognizedValue
from apps.ifc_validation_bff.report.value_formatting import (
    coerce_to_text, interpret_rule_value, outer_whitespace, pretty_file_size, truncate,
)


class GherkinValueTests(SimpleTestCase):
    def test_allowlisting_derives_a_pass_without_losing_original_severity(self):
        for severity in OutcomeSeverity:
            with self.subTest(severity=severity):
                outcome = Outcome(severity_in_db=severity, allowlisted=False)
                self.assertEqual(outcome.severity_after_whitelisting, severity)
                allowlisted = replace(outcome, allowlisted=True)
                self.assertEqual(allowlisted.severity_after_whitelisting, OutcomeSeverity.PASSED)
                self.assertEqual(allowlisted.severity_in_db, severity)
                self.assertEqual(replace(allowlisted, allowlisted=False).severity_after_whitelisting, severity)

    def test_primitives_are_not_cells(self):
        self.assertEqual(interpret_rule_value("a relationship"), "a relationship")
        self.assertEqual(interpret_rule_value({"value": 0}), AttributeValue(0))
        self.assertEqual(interpret_rule_value({"value": False}), AttributeValue(False))

    def test_ifc_concepts_have_named_fields(self):
        self.assertEqual(interpret_rule_value({"oneOf": ["IfcWall"], "context": "must be"}), AllowedValues(("IfcWall",), "must be"))
        self.assertEqual(interpret_rule_value({"entity": "IfcBeam(#22)"}), EntityReference("IfcBeam"))

    def test_empty_sequences_are_preserved_and_other_empty_values_are_omitted(self):
        for value in ((), []):
            self.assertIsInstance(interpret_rule_value(value), UnrecognizedValue)
            self.assertEqual(coerce_to_text(value), '[]')
        for value in ({}, None, "", 0, False):
            self.assertIsNone(interpret_rule_value(value))
            self.assertEqual(coerce_to_text(value), '')

    def test_formatting_matches_v1(self):
        self.assertEqual(coerce_to_text({"schema_identifier": "IFC4X3"}), '{"schema_identifier":"IFC4X3"}')
        self.assertEqual(pretty_file_size(1172), "1.14 kB")
        self.assertEqual(outer_whitespace("  name "), "□□name□")
        self.assertEqual(truncate("x" * 65), "x" * 61 + "...")
