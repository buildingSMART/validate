import pytest
import ifcopenshell
from pathlib import Path
from validate_header import HeaderStructure
from test_header_validation import collect_test_files

HERE = Path(__file__).parent


def details_for(relative_path):
    file = ifcopenshell.simple_spf.open(str(HERE / relative_path), only_header=True)
    header = HeaderStructure(file=file)
    return [(d['field'], d['expected'], d['observed']) for d in header.validation_details]


@pytest.mark.parametrize("f", collect_test_files())
def test_every_error_has_matching_detail(f):
    filename = f[0]
    header = HeaderStructure(file=ifcopenshell.simple_spf.open(filename, only_header=True))

    assert [d['field'] for d in header.validation_details] == header.validation_errors
    for detail in header.validation_details:
        assert set(detail) == {'field', 'expected', 'observed'}
        assert detail['expected']


def test_two_base_mvds_lists_both():
    details = details_for('tests/description/fail/two_mvds_in_separate_view_definitions_ifc4x3_add2.ifc')
    assert ('description', 'Exactly one base MVD (add-on views excluded)', 'Alignment-basedView, ReferenceView') in details


def test_unknown_mvd_lists_valid_ones_for_schema():
    details = details_for('tests/description/fail/outdated_mvd.ifc')  # CoordinationView + StructuralAnalysisView on IFC4X3_ADD2
    expected = 'One of the MVDs valid for IFC4X3_ADD2: ReferenceView, Alignment-basedView'
    assert ('description', expected, 'CoordinationView') in details
    assert ('description', expected, 'StructuralAnalysisView') in details


def test_add_on_view_without_coordination_view():
    details = details_for('tests/description/fail/add_on_view_without_coordination_view.ifc')
    assert ('description', 'Add-on views only in combination with CoordinationView', 'ViewDefinition [Custom, SpaceBoundary2ndLevelAddOnView]') in details


def test_missing_mvd_reports_raw_description():
    assert ('description', 'One Model View Definition, declared as ViewDefinition [...]', '') in details_for('tests/description/fail/no_description.ifc')
    assert ('description', 'One Model View Definition, declared as ViewDefinition [...]', None) in details_for('tests/description/fail/empty_description.ifc')


def test_originating_system_not_in_three_parts():
    details = details_for('tests/originating_system/fail/os_not_meaningful.ifc')
    fields = [field for field, _, _ in details]
    assert fields[0] == 'originating_system'
    assert details[0][1] == 'Software Company Name - Application Name - Application Version'
    # company and application name cannot be derived, so they are reported as missing
    assert ('company_name', 'Software Company Name from Originating System: not empty, no dashes, no leading or trailing whitespace', None) in details
    assert ('application_name', 'Application Name from Originating System: not empty, no dashes, no leading or trailing whitespace', None) in details


def test_whitespace_is_kept_in_observed_value():
    observed = [o for field, _, o in details_for('tests/company_name/fail/leading_whitespace.ifc') if field == 'company_name']
    assert observed and observed[0] != observed[0].strip()


def test_invalid_time_stamp():
    details = details_for('tests/time_stamp/fail/invalid_month.ifc')
    assert any(field == 'time_stamp' and expected.startswith('A date and time in ISO 8601 format') for field, expected, _ in details)


def test_syntax_error_has_no_details():
    header = HeaderStructure(file=None, validation_errors=["syntax_error"])
    assert header.validation_details == []


def test_same_mvd_declared_twice_counts_as_two_base_mvds():
    assert ('description', 'Exactly one base MVD (add-on views excluded)', 'ReferenceView, ReferenceView') in details_for('tests/description/fail/same_view_declared_twice_ifc4x3_add2.ifc')


def test_two_mvds_in_one_view_definition():
    assert ('description', 'Exactly one base MVD (add-on views excluded)', 'Alignment-basedView, ReferenceView') in details_for('tests/description/fail/two_mvds_in_one_view_definition_ifc4x3_add2.ifc')


PEP440 = 'Application Version from Originating System according to PEP 440: numbers and dots, optionally followed by -alpha, -beta or -rc'


@pytest.mark.parametrize("fixture, observed", [
    ('tests/version/fail/comma_separated_version.ifc', '26,0,0,0'),
    ('tests/version/fail/invalid_specifier.ifc', '26.0.0-final'),
    ('tests/version/fail/only-letters.ifc', 'twopointone'),
])
def test_version_not_pep440(fixture, observed):
    assert ('version', PEP440, observed) in details_for(fixture)


def test_version_trailing_whitespace():
    assert ('version', 'Application Version from Originating System: no leading or trailing whitespace', '26.0.0.0 ') in details_for('tests/version/fail/trailing_whitespace.ifc')


def test_company_name_with_dash():
    assert ('company_name', 'Software Company Name from Originating System: not empty, no dashes, no leading or trailing whitespace', 'Company-') in details_for('tests/company_name/fail/contains_dashes.ifc')
