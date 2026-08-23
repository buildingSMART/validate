import functools
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

import ifcopenshell
from django import forms
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    F,
    FloatField,
    Q,
    Value,
    When,
)
from django.db.models.functions import Cast
from django.db.models.fields.json import KeyTextTransform
from django.template.defaultfilters import floatformat

from apps.ifc_validation.checks.statistics.apply_mvd import TEMPLATES_DIR
from apps.ifc_validation_models.models import (
    EntityCountHistogram,
    Model,
    PsetCountHistogram,
    TemplateStatistic,
)

from apps.ifc_validation.statistics_query_concepts import (
    CONCEPT,
    CONCEPTS,
    EXPRESSION_OPERATOR,
    EXPRESSION_OPERATORS,
    FUNCTION,
    FUNCTIONS,
    OPERAND,
    OPERANDS,
    OPERATION,
    OPERATIONS,
    ORDERING,
    ORDERINGS,
    QUERY_OPERATOR,
    QUERY_OPERATORS,
    SOURCE,
    SOURCES,
    QueryFilter,
    StatisticsExpression,
    StatisticsQuery,
    choices,
)
from apps.ifc_validation.statistics_query_examples import EXAMPLES


class StatisticsSourceForm(forms.Form):
    source = forms.ChoiceField(choices=choices(SOURCES))


class StatisticsQueryClauseForm(forms.Form):
    OPERATION_CHOICES = choices(OPERATIONS)
    operation = forms.ChoiceField(choices=OPERATION_CHOICES)
    target = forms.ChoiceField(choices=[
        *((f"filter:{concept.name}", concept.label) for concept in CONCEPTS if "filter" in concept.acts_in),
        *((f"group:{concept.name}", concept.label) for concept in CONCEPTS if "group" in concept.acts_in),
        *((f"order:{ordering.name}", ordering.label) for ordering in ORDERINGS),
    ], required=False)
    operator = forms.ChoiceField(choices=choices(QUERY_OPERATORS), required=False)
    value = forms.CharField(max_length=1024, required=False)
    expression_function = forms.ChoiceField(
        choices=choices(FUNCTIONS),
        required=False,
        widget=forms.Select(attrs={"aria-label": "Function"}),
    )
    operand_a = forms.ChoiceField(
        choices=[("", "𝑎"), *choices(OPERANDS)],
        required=False,
        widget=forms.Select(attrs={"aria-label": "Operand A"}),
    )
    expression_operator = forms.ChoiceField(
        choices=choices(EXPRESSION_OPERATORS),
        required=False,
        widget=forms.Select(attrs={"aria-label": "Operator"}),
    )
    operand_b = forms.ChoiceField(
        choices=[("", "𝑏"), *choices(OPERANDS)],
        required=False,
        widget=forms.Select(attrs={"aria-label": "Operand B"}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned

        operation = cleaned.get("operation")
        target = cleaned.get("target")
        operator = cleaned.get("operator")
        value = cleaned.get("value", "").strip()
        if not operation:
            return cleaned

        if operation == "limit":
            if value.casefold() == "all":
                cleaned["resolved_value"] = None
                return cleaned
            try:
                limit = int(value)
                if not 1 <= limit <= 1000:
                    raise ValueError
            except ValueError:
                self.add_error("value", "Limit must be between 1 and 1000, or all.")
            else:
                cleaned["resolved_value"] = limit
            return cleaned

        if operation == "expression":
            operand_a = cleaned.get("operand_a")
            expression_operator = cleaned.get("expression_operator")
            operand_b = cleaned.get("operand_b")
            if not operand_a:
                self.add_error("operand_a", "Select operand A.")
            if expression_operator and not operand_b:
                self.add_error("operand_b", "Select operand B.")
            if operand_b and not expression_operator:
                self.add_error("expression_operator", "Select an operator.")
            cleaned["resolved_value"] = StatisticsExpression(
                cleaned.get("expression_function"), operand_a,
                expression_operator, operand_b,
            )
            return cleaned

        expected_prefix = f"{operation}:"
        if not target or not target.startswith(expected_prefix):
            self.add_error("target", "Select a value for this operation.")
            return cleaned
        resolved_value = target.removeprefix(expected_prefix)
        cleaned["resolved_value"] = resolved_value
        if operation == "group" and resolved_value == "graph_value":
            if not value:
                self.add_error("value", "Enter a JSON graph path.")
            elif not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*",
                value,
            ):
                self.add_error("value", "Enter a dotted JSON path using field names.")
            else:
                cleaned["resolved_value"] = f"graph_value:{value}"
            return cleaned
        if operation != "filter":
            return cleaned

        field = resolved_value
        concept = CONCEPT[field]
        if not operator:
            self.add_error("operator", "Select an operator.")
        elif operator not in concept.operators:
            self.add_error("operator", "This operator is not available for the selected field.")
        if not value:
            self.add_error("value", "Enter a value.")
            return cleaned

        try:
            typed_value = concept.parse(value)
            if field == "model" and not Model.objects.filter(pk=typed_value).exists():
                self.add_error("value", "No model with this ID exists.")
        except ValueError:
            self.add_error("value", f"Invalid value for {concept.label}.")
        else:
            cleaned["value"] = value
            cleaned["typed_value"] = typed_value
        return cleaned

StatisticsQueryClauseFormSet = forms.formset_factory(
    StatisticsQueryClauseForm,
    extra=0,
    can_delete=True,
    max_num=50,
    validate_max=True,
)


def build_statistics_expression(selection):
    """Compatibility helper for callers that have structured expression form data."""
    return StatisticsExpression(**selection).source


def model_histogram_query(source, model_id):
    if source not in {"entity", "pset"}:
        raise ValueError(f"Unsupported model histogram source {source!r}.")
    return StatisticsQuery(
        source,
        ("entity", "pset_name", "standardized") if source == "pset" else ("entity",),
        StatisticsExpression("sum"),
        limit=None,
        filters=(QueryFilter("model", "eq", model_id),),
    )


def query_form_clauses(query):
    clauses = [
        {"operation": "filter", "target": f"filter:{item.concept}",
         "operator": item.operator, "value": CONCEPT[item.concept].serialize(item.value)}
        for item in query.filters
    ]
    for group in query.groups:
        concept, _, graph_path = group.partition(":")
        clause = {"operation": "group", "target": f"group:{concept}"}
        if graph_path:
            clause["value"] = graph_path
        clauses.append(clause)
    clauses.extend((
        {"operation": "expression", "expression_function": query.expression.function,
         "operand_a": query.expression.operand_a,
         "expression_operator": query.expression.operator,
         "operand_b": query.expression.operand_b},
        {"operation": "order", "target": f"order:{query.ordering}"},
        {"operation": "limit", "value": query.limit if query.limit is not None else "all"},
    ))
    return clauses


def bind_statistics_query_form_data(query):
    clauses = query_form_clauses(query)
    data = {
        "source": query.source,
        "clauses-TOTAL_FORMS": len(clauses),
        "clauses-INITIAL_FORMS": 0,
        "clauses-MIN_NUM_FORMS": 0,
        "clauses-MAX_NUM_FORMS": 50,
    }
    for index, clause in enumerate(clauses):
        for field, value in clause.items():
            data[f"clauses-{index}-{field}"] = value
    return data


def build_statistics_specification(source, clause_formset):
    clauses = [
        form.cleaned_data
        for form in clause_formset.forms
        if form.cleaned_data and not form.cleaned_data.get("DELETE")
    ]
    operations = {
        operation: [clause for clause in clauses if clause["operation"] == operation]
        for operation in OPERATION
    }
    if not operations["group"]:
        raise ValueError("The query requires at least one group clause.")
    if len(operations["expression"]) != 1:
        raise ValueError("The query requires exactly one expression clause.")
    for operation in ("order", "limit"):
        if len(operations[operation]) > 1:
            raise ValueError(f"The query accepts at most one {operation} clause.")

    return StatisticsQuery(
        source=source,
        groups=tuple(
            clause["resolved_value"]
            for clause in operations["group"]
        ),
        expression=operations["expression"][0]["resolved_value"],
        ordering=(
            operations["order"][0]["resolved_value"]
            if operations["order"] else "descending"
        ),
        limit=operations["limit"][0]["resolved_value"] if operations["limit"] else None,
        filters=tuple(
            QueryFilter(clause["resolved_value"], clause["operator"], clause["typed_value"])
            for clause in operations["filter"]
        ),
    )


def _example_clause_context(clause):
    operation = clause["operation"]
    if operation == "expression":
        expression = StatisticsExpression(
            clause["expression_function"], clause["operand_a"],
            clause["expression_operator"], clause["operand_b"],
        )
        return {
            "operation": OPERATION[operation].label,
            "expression": {
                "function": FUNCTION[expression.function].label,
                "function_active": bool(expression.function),
                "operand_a": OPERAND[expression.operand_a].label,
                "operator": EXPRESSION_OPERATOR[expression.operator].label,
                "operator_active": bool(expression.operator),
                "operand_b": OPERAND[expression.operand_b].label if expression.operand_b else "𝑏",
                "operand_b_active": bool(expression.operand_b),
            },
            "form": clause,
        }
    if operation == "limit":
        return {"operation": OPERATION[operation].label, "selection": str(clause["value"]),
                "operator": "", "value": "", "form": clause}
    _, target = clause["target"].split(":", 1)
    selection = ORDERING[target].label if operation == "order" else CONCEPT[target].label
    return {"operation": OPERATION[operation].label, "selection": selection,
            "operator": QUERY_OPERATOR[clause["operator"]].label if operation == "filter" else "",
            "value": clause.get("value", ""), "form": clause}


def _example_context(title, query):
    clauses = query_form_clauses(query)
    return {"title": title, "source": SOURCE[query.source].label,
            "clauses": [_example_clause_context(clause) for clause in clauses],
            "form_data": {"source": query.source, "clauses": clauses}}


STATISTICS_QUERY_EXAMPLES = [_example_context(*example) for example in EXAMPLES]


def statistics_query_ui_context():
    schemas = list(
        Model.objects.exclude(schema__isnull=True).exclude(schema="")
        .values_list("schema", flat=True).distinct().order_by("schema")
    )
    entity_names = set()
    for schema in schemas:
        try:
            entity_names.update(EntityCountHistogram.entity_names(schema))
        except RuntimeError:
            continue
    template_names = {
        path.name for path in TEMPLATES_DIR.glob("*.md")
    } | set(
        TemplateStatistic.objects.filter(graph__isnull=False)
        .values_list("template_name", flat=True)
        .distinct()
    )

    return {
        "statistics_query_examples": STATISTICS_QUERY_EXAMPLES,
        "clause_target_choices": {
            "filter": {
                source: [
                    {"value": f"filter:{concept.name}", "label": concept.label}
                    for concept in CONCEPTS if concept.supports("filter", source)
                ]
                for source in SOURCE
            },
            "group": {
                source: [
                    {"value": f"group:{concept.name}", "label": concept.label}
                    for concept in CONCEPTS if concept.supports("group", source)
                ]
                for source in SOURCE
            },
            "expression": [],
            "order": [
                {"value": f"order:{value}", "label": label}
                for value, label in choices(ORDERINGS)
            ],
            "limit": [],
        },
        "filter_operator_choices": {
            f"filter:{field}": [
                {"value": operator, "label": QUERY_OPERATOR[operator].label}
                for operator in concept.operators
            ]
            for field, concept in CONCEPT.items() if "filter" in concept.acts_in
        },
        "filter_suggestions": {
            "models": [
                (str(model.pk), f"#{model.pk} - {model.file_name}")
                for model in Model.objects.only("id", "file_name").order_by("-created")
            ],
            "schemas": [(schema, schema) for schema in schemas],
            "entities": [(name, name) for name in sorted(entity_names)],
            "templates": [
                (name, name.removesuffix(".md").replace("_", " "))
                for name in sorted(template_names)
            ],
        },
    }


@dataclass
class StatisticsQueryResult:
    columns: list[str]
    rows: list[list]
    sql: str

    @property
    def display_rows(self):
        return [
            [format_statistics_value(value) for value in row]
            for row in self.rows
        ]


def format_statistics_value(value):
    if isinstance(value, (float, Decimal)):
        return floatformat(value, "-2")
    return value


def format_sql(sql):
    try:
        import sqlparse
    except ImportError:
        return sql
    return sqlparse.format(
        sql,
        reindent=True,
        keyword_case="upper",
        identifier_case=None,
    )


class StatisticsQueryBuilder:
    """Translate the canonical query into reusable Django query patterns."""

    def __init__(self, specification):
        self.spec = specification
        self.source = SOURCE[specification.source]
        self.filters = specification.filters
        self.groups = specification.groups
        self.schema = self.resolve_schema()

    def resolve_schema(self):
        model_ids = {
            clause.value
            for clause in self.filters
            if clause.concept == "model" and clause.operator == "eq"
        }
        schemas = {
            clause.value
            for clause in self.filters
            if clause.concept == "schema" and clause.operator == "eq"
        }
        if len(model_ids) > 1 or len(schemas) > 1:
            raise ValueError("Entity resolution requires one model or one exact schema filter.")

        model_schema = None
        if model_ids:
            model = Model.objects.filter(pk=next(iter(model_ids))).only("schema").first()
            if model is None:
                raise ValueError("The selected model no longer exists.")
            model_schema = model.schema
        schema = next(iter(schemas), None)
        if model_schema and schema and model_schema != schema:
            raise ValueError("The model and schema filters refer to different schemas.")
        return model_schema or schema

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def subtype_indices(schema, base_type):
        schema_definition = ifcopenshell.schema_by_name(schema)
        indices = []
        for index, entity_name in enumerate(EntityCountHistogram.entity_names(schema)):
            declaration = schema_definition.declaration_by_name(entity_name)
            while declaration:
                declaration = declaration.supertype()
                if declaration and declaration.name() == base_type:
                    indices.append(index)
                    break
        return tuple(indices)

    def base_queryset(self):
        query = self.source.queryset()
        for clause in self.filters:
            query = self.apply_filter(query, clause)
        return query

    def apply_filter(self, query, clause):
        concept = CONCEPT[clause.concept]
        if not concept.supports("filter", self.source.name):
            raise ValueError(
                f"Filter {concept.name!r} is not available for {self.source.name!r}.",
            )

        if concept.name == "entity":
            if not self.schema:
                raise ValueError("Entity filters require one model or one exact schema filter.")
            return self.apply_entity_filter(query, clause.operator, clause.value)
        if concept.name == "is_vendor":
            return self.apply_vendor_filter(
                query, clause.operator, clause.value, "model__",
            )
        return self.apply_lookup_filter(
            query, concept.lookup, clause.operator, clause.value,
        )

    @classmethod
    def apply_vendor_filter(cls, query, operator, value, model_prefix):
        vendor_status = Case(
            When(
                Q(**{
                    f"{model_prefix}uploaded_by__useradditionalinfo__is_vendor": True,
                })
                | Q(**{
                    f"{model_prefix}uploaded_by__useradditionalinfo__is_vendor_self_declared": True,
                }),
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
        query = query.annotate(statistics_is_vendor=vendor_status)
        return cls.apply_lookup_filter(
            query, "statistics_is_vendor", operator, value,
        )

    def apply_entity_filter(self, query, operator, entity_name):
        if operator in {"subtype_of", "not_subtype_of"}:
            indices = self.subtype_indices(self.schema, entity_name)
            if self.source.name == "template":
                values = [
                    EntityCountHistogram.string_from_index(self.schema, index)
                    for index in indices
                ]
                lookup = "focus_instance__ifc_type__in"
            else:
                values = indices
                lookup = "entity_index__in"
            method = "exclude" if operator == "not_subtype_of" else "filter"
            return getattr(query, method)(**{lookup: values})

        if operator not in {"eq", "ne"}:
            raise ValueError(f"Unsupported entity operator {operator!r}.")
        value = (
            entity_name
            if self.source.name == "template"
            else EntityCountHistogram.index_from_string(self.schema, entity_name)
        )
        lookup = "focus_instance__ifc_type" if self.source.name == "template" else "entity_index"
        method = "exclude" if operator == "ne" else "filter"
        return getattr(query, method)(**{lookup: value})

    @staticmethod
    def apply_lookup_filter(query, lookup, operator, value):
        try:
            operation = QUERY_OPERATOR[operator]
        except KeyError as error:
            raise ValueError(f"Unsupported operator {operator!r}.") from error
        if operation.special:
            raise ValueError(f"Operator {operator!r} requires an entity concept.")
        method = query.exclude if operation.negated else query.filter
        return method(**{f"{lookup}{operation.suffix}": value})

    def computed_model_count(self):
        models = Model.objects.all()
        for clause in self.filters:
            if clause.concept == "is_vendor":
                models = self.apply_vendor_filter(
                    models, clause.operator, clause.value, "",
                )
            elif clause.concept in {"model", "schema", "is_staff"}:
                lookup = {
                    "model": "pk",
                    "schema": "schema",
                    "is_staff": "uploaded_by__is_staff",
                }[clause.concept]
                models = self.apply_lookup_filter(
                    models, lookup, clause.operator, clause.value,
                )
        if self.source.name == "entity":
            models = models.filter(
                histogram_entries__count=EntityCountHistogram.COMPLETION_MARKER_COUNT,
            )
        elif self.source.name == "pset":
            models = models.filter(
                pset_count_entries__count=PsetCountHistogram.COMPLETION_MARKER_COUNT,
            )
        else:
            completion_markers = TemplateStatistic.objects.filter(
                graph__isnull=True,
            )
            for clause in self.filters:
                if clause.concept != "template":
                    continue
                completion_markers = self.apply_lookup_filter(
                    completion_markers, "template_name", clause.operator, clause.value,
                )
            models = models.filter(
                pk__in=completion_markers.values("model_id"),
            )
        return models.distinct().count()

    def grouped_queryset(self, base):
        fields = []
        labels = []
        for group_index, group in enumerate(self.groups):
            concept_name, _, argument = group.partition(":")
            try:
                concept = CONCEPT[concept_name]
            except KeyError as error:
                raise ValueError(f"Unsupported grouping {group!r}.") from error
            if not concept.supports("group", self.source.name):
                raise ValueError(
                    f"Unsupported grouping {group!r} for {self.source.name!r}.",
                )
            if concept_name == "entity":
                if self.source.name == "template":
                    group_fields, group_labels = ["focus_instance__ifc_type"], ["Entity"]
                else:
                    group_fields = ["model__schema", "entity_index"]
                    group_labels = ["Schema", "Entity"]
            elif concept_name == "graph_value":
                graph_path = argument
                alias = f"graph_value_{group_index}"
                lookup = f"graph__{graph_path.replace('.', '__')}"
                base = base.annotate(**{
                    alias: KeyTextTransform.from_lookup(lookup),
                })
                group_fields, group_labels = [alias], [f"Graph: {graph_path}"]
            elif concept_name == "proxy":
                if not self.schema:
                    raise ValueError(
                        "Proxy grouping requires entity counts and one schema or model.",
                    )
                proxy_indices = set(
                    self.subtype_indices(self.schema, "IfcBuildingElementProxy"),
                )
                proxy_indices.add(
                    EntityCountHistogram.index_from_string(
                        self.schema,
                        "IfcBuildingElementProxy",
                    )
                )
                base = base.annotate(
                    proxy_group=Case(
                        When(entity_index__in=proxy_indices, then=Value("Proxy")),
                        default=Value("Other element subtypes"),
                        output_field=CharField(),
                    )
                )
                group_fields, group_labels = ["proxy_group"], ["Category"]
            else:
                group_fields = list(concept.group_fields)
                group_labels = list(concept.result_labels)

            for field, label in zip(group_fields, group_labels):
                if field not in fields:
                    fields.append(field)
                    labels.append(label)
        return base, fields, labels

    def count_expression(self):
        return self.source.count_expression()

    def display_key(self, fields, values):
        displayed = list(values)
        schema = (
            values[fields.index("model__schema")]
            if "model__schema" in fields else self.schema
        )
        for index, field in enumerate(fields):
            if field == "entity_index":
                displayed[index] = (
                    EntityCountHistogram.string_from_index(schema, values[index])
                    if values[index] is not None else "Property definitions"
                )
            elif field == "is_standardized":
                displayed[index] = "Standard" if values[index] else "Custom"
            elif field == "pset_name" and not values[index]:
                displayed[index] = "(unnamed)"
            elif field == "model__produced_by_id" and values[index] is None:
                displayed[index] = "(unknown)"
            elif field == "model__produced_by__name" and not values[index]:
                displayed[index] = "(unknown)"
            elif field == "model__produced_by__version" and not values[index]:
                displayed[index] = "(unspecified)"
        return displayed

    def execute(self):
        base = self.base_queryset()
        grouped_base, fields, labels = self.grouped_queryset(base)
        expression = self.spec.expression
        expression.validate()
        limit = self.spec.limit
        descending = self.spec.ordering == "descending"
        count_expression = self.count_expression()

        if expression.is_average:
            return self.average_expression_result(
                grouped_base,
                fields,
                labels,
                count_expression,
                expression,
            )

        total_count = base.aggregate(total=count_expression)["total"] or 0
        computed_models = self.computed_model_count()
        query = grouped_base.values(*fields).annotate(
            source_count=count_expression,
            source_models=Count("model_id", distinct=True),
        )
        if expression.source == "count":
            query = query.annotate(value=F("source_count"))
        elif expression.source == "models":
            query = query.annotate(value=F("source_models"))
        else:
            expression_values = {
                "count": Cast(F("source_count"), FloatField()),
                "models": Cast(F("source_models"), FloatField()),
                "computed_models": Value(float(computed_models or 1)),
                "total_count": Value(float(total_count or 1)),
            }
            query = query.annotate(value=expression.compile(expression_values))

        query = query.order_by("-value" if descending else "value")
        if limit is not None:
            query = query[:limit]
        raw_rows = list(query.values_list(*fields, "value"))
        rows = [self.display_key(fields, row[:-1]) + [row[-1]] for row in raw_rows]
        return StatisticsQueryResult(
            labels + [expression.source],
            rows,
            format_sql(str(query.query)),
        )

    def average_expression_result(self, base, fields, labels, count_expression, expression):
        per_model = (
            base.values("model_id", *fields)
            .annotate(group_count=count_expression)
            .order_by()
        )
        records = list(per_model.values_list("model_id", *fields, "group_count"))
        totals = defaultdict(float)
        grouped = defaultdict(float)
        for record in records:
            model_id = record[0]
            key = tuple(record[1:-1])
            count = record[-1]
            totals[model_id] += count
            grouped[(model_id, key)] += count

        denominator = self.computed_model_count()
        total_count = sum(totals.values())
        averages = defaultdict(float)
        for (model_id, key), count in grouped.items():
            averages[key] += expression.evaluate({
                "count": count,
                "models": 1,
                "computed_models": denominator,
                "total_count": total_count,
                "model_total_count": totals[model_id],
            })
        rows = [
            self.display_key(fields, key) + [value / (denominator or 1)]
            for key, value in averages.items()
        ]
        rows.sort(key=lambda row: row[-1], reverse=self.spec.ordering == "descending")
        if self.spec.limit is not None:
            rows = rows[:self.spec.limit]
        return StatisticsQueryResult(
            labels + [expression.source],
            rows,
            format_sql(str(per_model.query)),
        )
