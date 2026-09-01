from collections import Counter
from pathlib import Path

from apps.ifc_validation.checks.statistics.apply_mvd import (
    available_template_names,
    extract_template_statistics,
)


FIXTURES = Path(__file__).parent


def test_column_property_set_statistics():
    results = extract_template_statistics(FIXTURES / "ColumnPSetsOfSets.ifc")

    property_type_results = [
        result
        for result in results
        if result["template"] == "Use_of_property_types.md"
    ]
    definition_set_results = [
        result
        for result in results
        if result["template"] == "Usage_of_IfcPropertySetDefinitionSet.md"
    ]
    expected_property_projection_names = Counter({
        "Pset_SpaceCommon": 8,
        "Pset_BuildingStoreyCommon": 6,
        "Pset_ColumnCommon": 4,
        "Pset_SiteCommon": 1,
        "Pset_EnvironmentalImpactIndicators": 1,
        "Pset_ReinforcementBarPitchOfColumn": 1,
        "Pset_BuildingCommon": 3,
        "Pset_BuildingElementProxyCommon": 2,
        "Pset_BuildingSystemCommon": 1,
        "PSet_1": 1,
        "PSet_2": 1,
    })
    expected_definition_set_results = [{
        "template": "Usage_of_IfcPropertySetDefinitionSet.md",
        "focus_step_id": 139,
        "focus_ifc_type": "IfcRelDefinesByProperties",
        "graph": {
            "IfcPropertySetDefinitionSet": "IfcPropertySetDefinitionSet",
        },
    }]

    assert Counter(result["template"] for result in results) == Counter({
        "Use_of_property_types.md": sum(
            expected_property_projection_names.values()
        ),
        "Usage_of_IfcPropertySetDefinitionSet.md": len(
            expected_definition_set_results
        ),
    })
    assert {
        result["focus_ifc_type"] for result in property_type_results
    } == {"IfcPropertySet"}
    assert {
        result["graph"]["PropertyType"] for result in property_type_results
    } == {"IfcPropertySingleValue"}
    assert Counter(
        result["graph"]["PropertySetName"]
        for result in property_type_results
    ) == expected_property_projection_names
    assert definition_set_results == expected_definition_set_results


def test_ifc2x3_curve_style_statistics():
    results = extract_template_statistics(FIXTURES / "pass-IfcCurveStyle-ifc2x3.ifc")

    assert results == [{
        "template": "Usage_of_bylayer_IfcCurveStyle.md",
        "focus_step_id": 1,
        "focus_ifc_type": "IfcCurveStyle",
        "graph": {"IfcDescriptiveMeasure": "IfcDescriptiveMeasure"},
    }]


def test_extraction_can_be_limited_to_missing_template_names():
    assert "Use_of_property_types.md" in available_template_names()

    results = extract_template_statistics(
        FIXTURES / "ColumnPSetsOfSets.ifc",
        template_names=("Usage_of_transition_curves_geometry.md",),
    )

    assert results == []
