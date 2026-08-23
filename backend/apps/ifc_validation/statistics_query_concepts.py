"""
This module offers a runtime builder mechanism for composing queries that assess
statistics on IFC models or sets of models.

These tasks are background tasks and every data model offers a way to record a
'completion marker' (multiple in case of the templates) so that computation of
statistics happens outside of the user-facing flow and can be scheduled at times
of low CPU usage.

At its basis are three database tables, populated by corresponding tasks, that
can be queried.

== entity

An aggregated count of entities (e.g. IfcWall) found in the model, with
materialized inheritance (e.g. IfcRoot).

| Field          | Meaning |
|----------------|---------|
| model          | The IFC model to which the histogram row belongs. |
| entity_index   | Index into the alphabetically sorted entity names for the model's IFC schema. |
| is_supertype   | False for concrete instances, true for counts materialized from subtype instances, and null for the completion marker. |
| count          | Number of matching instances; zero identifies the completion marker. |

== pset

An aggregated count of property- and quantity-set names (e.g. Pset_WallCommon) as:

- Independent property-set definitions, irrespective of association to elements.
- Property-set definitions as they are associated with elements and element types.

In case of schema-predefined property sets the entity name is used.

| Field           | Meaning |
|-----------------|---------|
| model           | The IFC model to which the histogram row belongs. |
| entity_index    | Null for independent definitions; otherwise the schema entity index of the associated object type. |
| pset_name       | Property- or quantity-set name; an empty string represents an unnamed set. |
| is_standardized | Whether the name occurs in the schema's property-set definitions. |
| count           | Number of definitions or associated objects; zero identifies the completion marker. |

== template

In various cases we are interested in usage patterns such as the parent or basis
curves of geometrical entities. This requires concept templates, identical in
form to those in the IFC 4.3+ specification, that are applied as graph queries
to the model.

| Field          | Meaning |
|----------------|---------|
| model          | The IFC model to which the statistic row belongs. |
| template_name  | Filename of the Markdown concept template that produced the row. |
| focus_instance | Model instance matched as the focus of the template; null on completion markers. |
| graph          | JSON object containing matched graph bindings; null identifies completion for this model and template. |

== query builder concepts

| Name           | Label                         | Acts in          | Valid sources          | Filter operators |
|----------------|-------------------------------|------------------|------------------------|------------------|
| model          | Model ID                      | filter, group    | entity, pset, template | eq, ne |
| schema         | IFC schema                    | filter, group    | entity, pset, template | eq, ne, contains, not_contains |
| entity         | Entity                        | filter, group    | entity, pset, template | eq, ne, subtype_of, not_subtype_of |
| count          | Count                         | filter           | entity, pset           | eq, ne, gt, gte, lt, lte |
| entity_kind    | Entity row type               | filter           | entity                 | eq, ne |
| pset_name      | Property-set name             | filter, group    | pset                   | eq, ne, contains, not_contains |
| pset_scope     | Property-set scope            | filter           | pset                   | eq, ne |
| standardized   | Standardized / custom         | filter, group    | pset                   | eq, ne |
| is_vendor      | Uploader is vendor            | filter           | entity, pset, template | eq, ne |
| is_staff       | Uploader is staff             | filter           | entity, pset, template | eq, ne |
| proxy          | Proxy / other element subtype | group            | entity                 | — |
| template       | Template                      | filter, group    | template               | eq, ne, contains, not_contains |
| authoring_tool | Authoring tool                | group            | template               | — |
| graph_value    | Template graph value          | group            | template               | — |

"""

import operator
from dataclasses import dataclass

from django.db.models import Count, ExpressionWrapper, FloatField, Sum, Value

from apps.ifc_validation_models.models import (
    EntityCountHistogram,
    PsetCountHistogram,
    TemplateStatistic,
)


ALL_SOURCES = frozenset({"entity", "pset", "template"})


@dataclass(frozen=True)
class NamedChoice:
    name: str
    label: str


@dataclass(frozen=True)
class QueryOperator(NamedChoice):
    suffix: str = ""
    negated: bool = False
    special: bool = False


@dataclass(frozen=True)
class ExpressionOperator(NamedChoice):
    symbol: str = ""
    function: object = None


@dataclass(frozen=True)
class Concept(NamedChoice):
    """One vocabulary entry used by forms, validation and query construction."""

    acts_in: frozenset
    valid_sources: frozenset = ALL_SOURCES
    operators: tuple = ()
    lookup: str | None = None
    values: tuple = ()
    value_type: str = "text"
    group_fields: tuple = ()
    result_labels: tuple = ()

    def supports(self, operation, source):
        return operation in self.acts_in and source in self.valid_sources

    def parse(self, value):
        if self.values:
            try:
                return dict(self.values)[value.casefold()]
            except KeyError as error:
                raise ValueError from error
        if self.value_type == "non_negative_integer":
            parsed = int(value)
            if parsed < 0:
                raise ValueError
            return parsed
        return value

    def serialize(self, value):
        for name, parsed in self.values:
            if parsed == value:
                return name
        return str(value)


@dataclass(frozen=True)
class StatisticsSource(NamedChoice):
    model: type
    conditions: tuple
    count_field: str | None

    def queryset(self):
        return self.model.objects.filter(**dict(self.conditions))

    def count_expression(self):
        return Sum(self.count_field) if self.count_field else Count("pk")


@dataclass(frozen=True)
class QueryFilter:
    concept: str
    operator: str
    value: object


@dataclass(frozen=True)
class StatisticsExpression:
    function: str = ""
    operand_a: str = "count"
    operator: str = ""
    operand_b: str = ""

    NAMES = frozenset({
        "count", "computed_models", "total_count", "model_total_count", "1", "100",
    })

    def validate(self):
        if self.function not in FUNCTION or self.operand_a not in OPERAND:
            raise ValueError("Unsupported expression function or operand.")
        if self.operator not in EXPRESSION_OPERATOR:
            raise ValueError("Unsupported expression operator.")
        if bool(self.operator) != bool(self.operand_b):
            raise ValueError("An expression operator and operand B must be used together.")
        if self.function == "average":
            if {self.operand_a, self.operand_b} - {""} <= {
                "count", "model_total_count", "1", "100",
            }:
                return
            raise ValueError("Unsupported AVG expression.")
        if self.function == "sum":
            if not self.operator and self.operand_a == "count":
                return
            raise ValueError("Unsupported SUM expression.")
        if self.function == "count_distinct":
            if not self.operator and self.operand_a == "model":
                return
            raise ValueError("Unsupported COUNT DISTINCT expression.")
        operands = {self.operand_a, self.operand_b} - {""}
        if not operands <= self.NAMES or "model_total_count" in operands:
            raise ValueError("Unsupported expression operand.")

    @property
    def source(self):
        self.validate()
        expression = self.operand_a
        if self.operator:
            operation = EXPRESSION_OPERATOR[self.operator]
            expression = f"{expression} {operation.symbol} {self.operand_b}"
        if not self.function:
            return expression
        if self.function == "average":
            return f"avg({expression})"
        return "count" if self.function == "sum" else "models"

    @property
    def is_average(self):
        return self.function == "average"

    @property
    def names(self):
        self.validate()
        return {name for name in (self.operand_a, self.operand_b) if name in self.NAMES}

    def _operand(self, name, values, orm=False):
        if name in {"1", "100"}:
            number = float(name)
            return Value(number) if orm else number
        return values[name]

    def compile(self, values):
        self.validate()
        expression = self._operand(self.operand_a, values, orm=True)
        if self.operator:
            expression = EXPRESSION_OPERATOR[self.operator].function(
                expression, self._operand(self.operand_b, values, orm=True),
            )
        return ExpressionWrapper(expression, output_field=FloatField())

    def evaluate(self, values):
        self.validate()
        left = self._operand(self.operand_a, values)
        if not self.operator:
            return left
        try:
            return EXPRESSION_OPERATOR[self.operator].function(
                left, self._operand(self.operand_b, values),
            )
        except ZeroDivisionError:
            return 0


@dataclass(frozen=True)
class StatisticsQuery:
    source: str
    groups: tuple
    expression: StatisticsExpression = StatisticsExpression()
    ordering: str = "descending"
    limit: int | None = 10
    filters: tuple = ()


def _index(entries):
    return {entry.name: entry for entry in entries}


OPERATIONS = (
    NamedChoice("filter", "Filter"), NamedChoice("group", "Group by"),
    NamedChoice("expression", "Expression"), NamedChoice("order", "Order by"),
    NamedChoice("limit", "Limit"),
)
ORDERINGS = (
    NamedChoice("descending", "Descending"), NamedChoice("ascending", "Ascending"),
)
QUERY_OPERATORS = (
    QueryOperator("eq", "is"), QueryOperator("ne", "is not", negated=True),
    QueryOperator("gt", ">", "__gt"), QueryOperator("gte", ">=", "__gte"),
    QueryOperator("lt", "<", "__lt"), QueryOperator("lte", "<=", "__lte"),
    QueryOperator("contains", "contains", "__icontains"),
    QueryOperator("not_contains", "does not contain", "__icontains", True),
    QueryOperator("subtype_of", "is a subtype of", special=True),
    QueryOperator("not_subtype_of", "is not a subtype of", negated=True, special=True),
)
FUNCTIONS = (
    NamedChoice("", "𝑓"), NamedChoice("sum", "SUM"),
    NamedChoice("average", "AVG"), NamedChoice("count_distinct", "COUNT DISTINCT"),
)
OPERANDS = (
    NamedChoice("count", "count"), NamedChoice("model", "model"),
    NamedChoice("computed_models", "computed models"),
    NamedChoice("total_count", "total count"),
    NamedChoice("model_total_count", "model total count"),
    NamedChoice("1", "1"), NamedChoice("100", "100"),
)
EXPRESSION_OPERATORS = (
    ExpressionOperator("", "op"),
    ExpressionOperator("add", "+", "+", operator.add),
    ExpressionOperator("subtract", "−", "-", operator.sub),
    ExpressionOperator("multiply", "×", "*", operator.mul),
    ExpressionOperator("divide", "÷", "/", operator.truediv),
)

_FILTER = frozenset({"filter"})
_GROUP = frozenset({"group"})
_BOTH = _FILTER | _GROUP
_ENTITY_PSET = frozenset({"entity", "pset"})
_BOOLEAN_VALUES = (("true", True), ("false", False))
CONCEPTS = (
    Concept("model", "Model ID", _BOTH, operators=("eq", "ne"), lookup="model_id",
            value_type="non_negative_integer", group_fields=("model_id", "model__file_name"),
            result_labels=("Model ID", "Model")),
    Concept("schema", "IFC schema", _BOTH, operators=("eq", "ne", "contains", "not_contains"),
            lookup="model__schema", group_fields=("model__schema",), result_labels=("Schema",)),
    Concept("entity", "Entity", _BOTH, operators=("eq", "ne", "subtype_of", "not_subtype_of")),
    Concept("count", "Count", _FILTER, _ENTITY_PSET,
            ("eq", "ne", "gt", "gte", "lt", "lte"), "count",
            value_type="non_negative_integer"),
    Concept("entity_kind", "Entity row type", _FILTER, frozenset({"entity"}),
            ("eq", "ne"), "is_supertype", (("concrete", False), ("inherited", True))),
    Concept("pset_name", "Property-set name", _BOTH, frozenset({"pset"}),
            ("eq", "ne", "contains", "not_contains"), "pset_name",
            group_fields=("pset_name",), result_labels=("Property set",)),
    Concept("pset_scope", "Property-set scope", _FILTER, frozenset({"pset"}),
            ("eq", "ne"), "entity_index__isnull",
            (("definitions", True), ("associations", False))),
    Concept("standardized", "Standardized / custom", _BOTH, frozenset({"pset"}),
            ("eq", "ne"), "is_standardized",
            (("standard", True), ("true", True), ("custom", False), ("false", False)),
            group_fields=("is_standardized",), result_labels=("Standardized",)),
    Concept("is_vendor", "Uploader is vendor", _FILTER,
            operators=("eq", "ne"), values=_BOOLEAN_VALUES),
    Concept("is_staff", "Uploader is staff", _FILTER,
            operators=("eq", "ne"), lookup="model__uploaded_by__is_staff",
            values=_BOOLEAN_VALUES),
    Concept("proxy", "Proxy / other element subtype", _GROUP, frozenset({"entity"})),
    Concept("template", "Template", _BOTH, frozenset({"template"}),
            ("eq", "ne", "contains", "not_contains"), "template_name",
            group_fields=("template_name",), result_labels=("Template",)),
    Concept("authoring_tool", "Authoring tool", _GROUP, frozenset({"template"}),
            group_fields=("model__produced_by_id", "model__produced_by__name",
                          "model__produced_by__version"),
            result_labels=("Authoring tool ID", "Authoring tool", "Version")),
    Concept("graph_value", "Template graph value", _GROUP, frozenset({"template"})),
)
SOURCES = (
    StatisticsSource("entity", "Entity counts", EntityCountHistogram,
                     (("count__gt", 0), ("is_supertype__isnull", False)), "count"),
    StatisticsSource("pset", "Property-set counts", PsetCountHistogram,
                     (("count__gt", 0),), "count"),
    StatisticsSource("template", "Template statistics", TemplateStatistic,
                     (("graph__isnull", False),), None),
)

OPERATION = _index(OPERATIONS)
ORDERING = _index(ORDERINGS)
QUERY_OPERATOR = _index(QUERY_OPERATORS)
FUNCTION = _index(FUNCTIONS)
OPERAND = _index(OPERANDS)
EXPRESSION_OPERATOR = _index(EXPRESSION_OPERATORS)
CONCEPT = _index(CONCEPTS)
SOURCE = _index(SOURCES)


def choices(entries):
    return [(entry.name, entry.label) for entry in entries]
