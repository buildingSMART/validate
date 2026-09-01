from apps.ifc_validation.statistics_query_concepts import (
    QueryFilter,
    StatisticsAnnotation,
    StatisticsExpression,
    StatisticsQuery,
)


def example(title, source, groups, filters=(), expression=StatisticsExpression(), limit=10,
            annotations=()):
    return title, StatisticsQuery(
        source, groups, expression, limit=limit, filters=filters,
        annotations=annotations,
    )


PROXY_RATIO_ANNOTATIONS = (
    StatisticsAnnotation(
        "proxy_count",
        filters=(QueryFilter("entity", "eq", "IfcBuildingElementProxy"),),
    ),
    StatisticsAnnotation(
        "building_element_count",
        filters=(QueryFilter("entity", "eq", "IfcBuildingElement"),),
    ),
)


EXAMPLES = (
    example("Top 10 element subtypes used in one file", "entity", ("entity",),
            (QueryFilter("model", "eq", 123), QueryFilter("entity", "subtype_of", "IfcElement"),
             QueryFilter("entity_kind", "eq", False)), StatisticsExpression("sum")),
    example("Average top 10 element subtypes used in files of an IFC version", "entity", ("entity",),
            (QueryFilter("schema", "eq", "IFC4"), QueryFilter("entity", "subtype_of", "IfcElement"),
             QueryFilter("entity_kind", "eq", False)), StatisticsExpression("average")),
    example("Number of files of an IFC version containing an entity", "entity", (),
            (QueryFilter("schema", "eq", "IFC4"), QueryFilter("entity", "eq", "IfcWall"),
             QueryFilter("entity_kind", "eq", False)),
            StatisticsExpression("count_distinct", "model"), limit=None),
    example("Top 10 property sets used in one file", "pset", ("pset_name",),
            (QueryFilter("model", "eq", 123), QueryFilter("pset_scope", "eq", True)),
            StatisticsExpression("sum")),
    example("Average top 10 property sets used in files of an IFC version", "pset", ("pset_name",),
            (QueryFilter("schema", "eq", "IFC4"), QueryFilter("pset_scope", "eq", True)),
            StatisticsExpression("average")),
    example("Ratio of standard versus custom property sets in one file", "pset", ("standardized",),
            (QueryFilter("model", "eq", 123), QueryFilter("pset_scope", "eq", True)),
            StatisticsExpression(operator="divide", operand_b="total_count")),
    example("Average ratio of standard versus custom property sets by IFC version", "pset",
            ("standardized",),
            (QueryFilter("schema", "eq", "IFC4"), QueryFilter("pset_scope", "eq", True)),
            StatisticsExpression("average", operator="divide", operand_b="model_total_count")),
    example("Proxy ratio in one file", "entity", (),
            (QueryFilter("model", "eq", 123),),
            StatisticsExpression(operand_a="proxy_count", operator="divide",
                                 operand_b="building_element_count"),
            limit=None, annotations=PROXY_RATIO_ANNOTATIONS),
    example("Average proxy ratio in files of an IFC version", "entity", (),
            (QueryFilter("schema", "eq", "IFC4"),),
            StatisticsExpression("average", operand_a="proxy_count", operator="divide",
                                 operand_b="building_element_count"),
            limit=None, annotations=PROXY_RATIO_ANNOTATIONS),
    example("Property type counts grouped by AuthoringTool", "template",
            ("authoring_tool", "graph_value:PropertyType"),
            (QueryFilter("template", "eq", "Use_of_property_types.md"),),
            StatisticsExpression("sum"), limit=None),
    example("Property type counts for a single model", "template", ("graph_value:PropertyType",),
            (QueryFilter("model", "eq", 123),
             QueryFilter("template", "eq", "Use_of_property_types.md")),
            StatisticsExpression("sum"), limit=None),
    example("Basis counts grouped by AuthoringTool", "template",
            ("authoring_tool", "graph_value:ParentCurve"),
            (QueryFilter("template", "eq", "Usage_of_transition_curves_geometry.md"),),
            StatisticsExpression("sum"), limit=None),
    example("Basis type counts for a single model", "template", ("graph_value:ParentCurve",),
            (QueryFilter("model", "eq", 123),
             QueryFilter("template", "eq", "Usage_of_transition_curves_geometry.md")),
            StatisticsExpression("sum"), limit=None),
)
