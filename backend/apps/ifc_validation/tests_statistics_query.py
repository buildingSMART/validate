from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse

from apps.ifc_validation.checks.statistics.apply_mvd import available_template_names
from apps.ifc_validation.statistics_query import (
    CONCEPTS,
    SOURCES,
    QueryFilter,
    StatisticsExpression,
    StatisticsQuery,
    StatisticsQueryClauseForm,
    StatisticsQueryBuilder,
    build_statistics_expression,
    format_sql,
    format_statistics_value,
    statistics_query_ui_context,
)
from apps.ifc_validation.tasks.statistics_tasks import (
    extract_entity_histogram_in_subprocess,
    extract_pset_histogram_in_subprocess,
    extract_template_statistics_in_subprocess,
    populate_entity_count_histogram,
    populate_pset_count_histogram,
    populate_template_statistics,
    pset_resource_schema,
    schedule_model_statistic_tasks,
    standardized_pset_names,
)
from apps.ifc_validation_models.models import (
    AuthoringTool,
    EntityCountHistogram,
    Model,
    ModelInstance,
    PsetCountHistogram,
    TemplateStatistic,
)


class StatisticsValueTests(SimpleTestCase):
    def test_celery_beat_uses_the_renamed_statistics_task_module(self):
        schedule = settings.CELERY_BEAT_SCHEDULE[
            "schedule-model-statistic-tasks-every-15min"
        ]

        assert schedule["task"] == (
            "apps.ifc_validation.tasks.statistics_tasks."
            "schedule_model_statistic_tasks"
        )
        assert schedule_model_statistic_tasks.name == schedule["task"]

    def test_clause_operations_use_expression_and_keep_source_separate(self):
        operations = dict(StatisticsQueryClauseForm.OPERATION_CHOICES)
        form = StatisticsQueryClauseForm()

        assert operations["expression"] == "Expression"
        assert "express" not in operations
        assert "select" not in operations
        assert "source" not in operations
        assert dict(form.fields["expression_function"].choices)[""] == "𝑓"
        assert dict(form.fields["operand_a"].choices)[""] == "𝑎"
        assert dict(form.fields["expression_operator"].choices)[""] == "op"
        assert dict(form.fields["operand_b"].choices)[""] == "𝑏"

    def test_structured_expressions_compile_to_internal_syntax(self):
        assert build_statistics_expression({
            "function": "",
            "operand_a": "count",
            "operator": "",
            "operand_b": "",
        }) == "count"
        assert build_statistics_expression({
            "function": "average",
            "operand_a": "count",
            "operator": "",
            "operand_b": "",
        }) == "avg(count)"
        assert build_statistics_expression({
            "function": "",
            "operand_a": "count",
            "operator": "divide",
            "operand_b": "computed_models",
        }) == "count / computed_models"
        assert build_statistics_expression({
            "function": "average",
            "operand_a": "count",
            "operator": "divide",
            "operand_b": "model_total_count",
        }) == "avg(count / model_total_count)"
        assert build_statistics_expression({
            "function": "count_distinct",
            "operand_a": "model",
            "operator": "",
            "operand_b": "",
        }) == "models"
        assert build_statistics_expression({
            "function": "sum",
            "operand_a": "count",
            "operator": "",
            "operand_b": "",
        }) == "count"

    def test_invalid_function_expression_is_left_to_the_backend(self):
        with self.assertRaisesRegex(ValueError, "Unsupported SUM expression"):
            build_statistics_expression({
                "function": "sum",
                "operand_a": "model",
                "operator": "",
                "operand_b": "",
            })

    def test_expression_operator_and_operand_b_are_an_optional_pair(self):
        single_operand = StatisticsQueryClauseForm(data={
            "operation": "expression",
            "operand_a": "count",
        })
        missing_operator = StatisticsQueryClauseForm(data={
            "operation": "expression",
            "operand_a": "count",
            "operand_b": "total_count",
        })
        missing_operand_b = StatisticsQueryClauseForm(data={
            "operation": "expression",
            "operand_a": "count",
            "expression_operator": "divide",
        })

        assert single_operand.is_valid()
        assert not missing_operator.is_valid()
        assert "expression_operator" in missing_operator.errors
        assert not missing_operand_b.is_valid()
        assert "operand_b" in missing_operand_b.errors

    def test_average_rejects_operands_unavailable_per_model(self):
        with self.assertRaisesRegex(ValueError, "Unsupported AVG expression"):
            build_statistics_expression({
                "function": "average",
                "operand_a": "count",
                "operator": "divide",
                "operand_b": "computed_models",
            })

    def test_template_graph_group_accepts_a_safe_dotted_json_path(self):
        form = StatisticsQueryClauseForm(data={
            "operation": "group",
            "target": "group:graph_value",
            "value": "Nested.PropertyType",
        })

        assert form.is_valid(), form.errors
        assert form.cleaned_data["resolved_value"] == (
            "graph_value:Nested.PropertyType"
        )

    def test_template_graph_group_rejects_an_invalid_json_path(self):
        form = StatisticsQueryClauseForm(data={
            "operation": "group",
            "target": "group:graph_value",
            "value": "PropertyType') OR TRUE --",
        })

        assert not form.is_valid()
        assert "value" in form.errors

    def test_dimension_values_are_not_treated_as_numbers(self):
        assert format_statistics_value("IFC4") == "IFC4"
        assert format_statistics_value("IfcWall") == "IfcWall"

    def test_numeric_values_are_compactly_formatted(self):
        assert format_statistics_value(575) == 575
        assert format_statistics_value(75.0) == "75"
        assert format_statistics_value(Decimal("12.345")) == "12.35"

    def test_structured_expression_evaluates_arithmetic_and_rejects_unknown_names(self):
        expression = StatisticsExpression(
            "average", "count", "divide", "model_total_count",
        )

        assert expression.is_average
        assert expression.names == {"count", "model_total_count"}
        assert expression.evaluate({"count": 2, "model_total_count": 8}) == .25
        with self.assertRaisesRegex(ValueError, "Unsupported expression"):
            StatisticsExpression(operand_a="__import__('os')").validate()
        with self.assertRaisesRegex(ValueError, "Unsupported expression"):
            StatisticsExpression(
                operand_a="count", operator="divide", operand_b="model_total_count",
            ).validate()

    def test_sql_uses_whitelist_style_formatting(self):
        sql = format_sql("select a from example where a = 1 order by a")

        assert sql.startswith("SELECT a")
        assert "\nFROM example" in sql
        assert "\nWHERE a = 1" in sql
        assert "\nORDER BY a" in sql


class StatisticsSubprocessTests(SimpleTestCase):
    statistics_fixtures = (
        Path(__file__).parent
        / "checks"
        / "statistics"
        / "tests"
    )

    def test_entity_and_pset_histograms_are_extracted_in_subprocesses(self):
        file_path = self.statistics_fixtures / "ColumnPSetsOfSets.ifc"

        entities = extract_entity_histogram_in_subprocess(str(file_path))
        psets = extract_pset_histogram_in_subprocess(str(file_path))

        assert entities["schema_identifier"] == "IFC2X3"
        assert any(
            entity_name == "IfcPropertySet" and not is_supertype and count > 0
            for entity_name, is_supertype, count in entities["entries"]
        )
        pset_counts = {
            (entity_name, pset_name): count
            for entity_name, pset_name, count in psets["entries"]
        }
        assert psets["schema_identifier"] == "IFC2X3"
        assert pset_counts[(None, "Pset_ColumnCommon")] == 2

    def test_template_statistics_are_extracted_in_a_subprocess(self):
        results = extract_template_statistics_in_subprocess(
            str(self.statistics_fixtures / "ColumnPSetsOfSets.ifc"),
            ("Use_of_property_types.md",),
        )

        assert len(results) == 17
        assert {result["template"] for result in results} == {
            "Use_of_property_types.md",
        }

    def test_pset_definition_resources_cover_schema_addenda(self):
        assert pset_resource_schema("IFC2X3_TC1") == "IFC2X3"
        assert pset_resource_schema("IFC4_ADD2") == "IFC4"
        assert pset_resource_schema("IFC4X3_ADD2") == "IFC4X3"
        assert "Pset_WallCommon" in standardized_pset_names("IFC4_ADD2")
        assert "Definitely_Custom" not in standardized_pset_names("IFC4_ADD2")


class StatisticsQueryBuilderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_superuser(
            username="statistics-query",
            email="statistics@example.com",
            password="unused",
        )
        cls.user = user
        cls.first = Model.objects.create(
            file_name="first.ifc",
            file="first.ifc",
            size=1,
            schema="IFC4",
            uploaded_by=user,
        )
        cls.second = Model.objects.create(
            file_name="second.ifc",
            file="second.ifc",
            size=1,
            schema="IFC4",
            uploaded_by=user,
        )

        indices = {
            name: EntityCountHistogram.index_from_string("IFC4", name)
            for name in (
                "IfcDoor", "IfcBuildingElementProxy", "IfcElement", "IfcProject",
                "IfcWall",
            )
        }
        EntityCountHistogram.objects.bulk_create([
            EntityCountHistogram(
                model=cls.first,
                entity_index=indices[name],
                count=count,
                is_supertype=False,
            )
            for name, count in (
                ("IfcWall", 10),
                ("IfcDoor", 5),
                ("IfcBuildingElementProxy", 2),
                ("IfcProject", 1),
            )
        ] + [
            EntityCountHistogram(
                model=cls.second,
                entity_index=indices[name],
                count=count,
                is_supertype=False,
            )
            for name, count in (("IfcWall", 30), ("IfcDoor", 5))
        ] + [
            EntityCountHistogram(
                model=model,
                entity_index=indices["IfcElement"],
                count=count,
                is_supertype=True,
            )
            for model, count in ((cls.first, 17), (cls.second, 35))
        ] + [
            EntityCountHistogram.completion_marker(model)
            for model in (cls.first, cls.second)
        ])
        PsetCountHistogram.objects.bulk_create([
            PsetCountHistogram(
                model=model,
                entity_index=None,
                pset_name=name,
                is_standardized=standardized,
                count=count,
            )
            for model, name, standardized, count in (
                (cls.first, "Pset_WallCommon", True, 8),
                (cls.first, "Custom_First", False, 2),
                (cls.second, "Pset_WallCommon", True, 2),
                (cls.second, "Custom_Second", False, 8),
            )
        ] + [
            PsetCountHistogram(
                model=model,
                entity_index=indices[entity],
                pset_name=name,
                is_standardized=standardized,
                count=count,
            )
            for model, entity, name, standardized, count in (
                (cls.first, "IfcWall", "Pset_WallCommon", True, 8),
                (cls.first, "IfcDoor", "Custom_First", False, 2),
                (cls.second, "IfcWall", "Pset_WallCommon", True, 2),
                (cls.second, "IfcDoor", "Custom_Second", False, 8),
            )
        ] + [
            PsetCountHistogram.completion_marker(model)
            for model in (cls.first, cls.second)
        ])

        first_wall = ModelInstance.objects.create(
            model=cls.first,
            stepfile_id=1,
            ifc_type="IfcWall",
        )
        first_door = ModelInstance.objects.create(
            model=cls.first,
            stepfile_id=2,
            ifc_type="IfcDoor",
        )
        second_wall = ModelInstance.objects.create(
            model=cls.second,
            stepfile_id=1,
            ifc_type="IfcWall",
        )
        TemplateStatistic.objects.bulk_create([
            TemplateStatistic(
                model=cls.first,
                template_name="Template_A.md",
                focus_instance=first_wall,
                graph={"value": "first wall"},
            ),
            TemplateStatistic(
                model=cls.first,
                template_name="Template_A.md",
                focus_instance=first_door,
                graph={"value": "first door"},
            ),
            TemplateStatistic(
                model=cls.second,
                template_name="Template_A.md",
                focus_instance=second_wall,
                graph={"value": "second wall"},
            ),
            TemplateStatistic(
                model=cls.second,
                template_name="Template_B.md",
                focus_instance=second_wall,
                graph={"value": "second template"},
            ),
            *[
                TemplateStatistic(
                    model=model,
                    template_name=template_name,
                    graph=None,
                )
                for model in (cls.first, cls.second)
                for template_name in dict.fromkeys((
                    *available_template_names(),
                    "Template_A.md",
                    "Template_B.md",
                ))
            ],
        ])

    @staticmethod
    def execute(**overrides):
        specification = {
            "source": "entity",
            "group_by": "entity",
            "expression": "count",
            "ordering": "descending",
            "limit": 10,
            "filters": [{
                "field": "schema",
                "operator": "eq",
                "value": "IFC4",
                "typed_value": "IFC4",
            }],
        }
        specification.update(overrides)
        expressions = {
            "count": StatisticsExpression(),
            "avg(count)": StatisticsExpression("average"),
            "models": StatisticsExpression("count_distinct", "model"),
            "count / total_count": StatisticsExpression(
                operator="divide", operand_b="total_count",
            ),
            "count / computed_models": StatisticsExpression(
                operator="divide", operand_b="computed_models",
            ),
            "avg(count / model_total_count)": StatisticsExpression(
                "average", operator="divide", operand_b="model_total_count",
            ),
        }
        groups = specification["group_by"]
        if isinstance(groups, str):
            groups = (groups,)
        groups = tuple("pset_name" if group == "pset" else group for group in groups)
        query = StatisticsQuery(
            specification["source"],
            groups,
            expressions[specification["expression"]],
            specification["ordering"],
            specification["limit"],
            tuple(
                QueryFilter(clause["field"], clause["operator"], clause["typed_value"])
                for clause in specification["filters"]
            ),
        )
        return StatisticsQueryBuilder(query).execute()

    @staticmethod
    def clause(field, operator, value, typed_value=None):
        return {
            "field": field,
            "operator": operator,
            "value": str(value),
            "typed_value": value if typed_value is None else typed_value,
        }

    @staticmethod
    def expression(function="", operand_a="count", operator="", operand_b=""):
        return {
            "operation": "expression",
            "expression_function": function,
            "operand_a": operand_a,
            "expression_operator": operator,
            "operand_b": operand_b,
        }

    def post_query(self, clauses, source="entity"):
        self.client.force_login(self.user)
        data = {
            "source": source,
            "clauses-TOTAL_FORMS": len(clauses),
            "clauses-INITIAL_FORMS": 0,
            "clauses-MIN_NUM_FORMS": 0,
            "clauses-MAX_NUM_FORMS": 50,
        }
        for index, clause in enumerate(clauses):
            for field, value in clause.items():
                data[f"clauses-{index}-{field}"] = value
        return self.client.post(
            reverse("admin:ifc_validation_models_model_statistics"),
            data,
        )

    def test_zero_count_completion_markers_are_never_query_results(self):
        entity_result = self.execute(limit=100)
        pset_result = self.execute(
            source="pset",
            group_by="pset",
            limit=100,
            filters=[self.clause("schema", "eq", "IFC4")],
        )

        assert all(row[-1] > 0 for row in entity_result.rows)
        assert all(row[-1] > 0 for row in pset_result.rows)
        assert "(unnamed)" not in {row[0] for row in pset_result.rows}
        assert self.first.get_histogram()
        assert all(count > 0 for count in self.first.get_histogram().values())

    def test_empty_histogram_tasks_replace_rows_and_create_completion_markers(self):
        model = Model.objects.create(
            file_name="empty.ifc",
            file="empty.ifc",
            size=1,
            schema="IFC4",
            uploaded_by=self.user,
        )
        task_module = "apps.ifc_validation.tasks.statistics_tasks"
        with (
            patch(f"{task_module}.get_absolute_file_path", return_value="empty.ifc"),
            patch(
                f"{task_module}.extract_entity_histogram_in_subprocess",
                return_value={"schema_identifier": "IFC4", "entries": []},
            ) as extract_entities,
            patch(
                f"{task_module}.extract_pset_histogram_in_subprocess",
                return_value={"schema_identifier": "IFC4", "entries": []},
            ) as extract_psets,
        ):
            assert populate_entity_count_histogram.run(model.pk) == 0
            assert populate_pset_count_histogram.run(model.pk) == 0
            assert populate_entity_count_histogram.run(model.pk) == 0
            assert populate_pset_count_histogram.run(model.pk) == 0

        entity_marker = model.histogram_entries.get(count=0)
        pset_marker = model.pset_count_entries.get(count=0)
        assert entity_marker.is_completion_marker
        assert entity_marker.is_supertype is None
        assert pset_marker.is_completion_marker
        assert pset_marker.entity_index is None
        assert extract_entities.call_count == 2
        assert extract_psets.call_count == 2
        assert "histogram completed" in str(entity_marker)
        assert "histogram completed" in str(pset_marker)

    def test_histogram_data_rows_have_database_uniqueness_constraints(self):
        entity = self.first.histogram_entries.filter(
            count__gt=0,
            is_supertype=False,
        ).first()
        pset = self.first.pset_count_entries.filter(
            count__gt=0,
            entity_index__isnull=False,
        ).first()

        with self.assertRaises(IntegrityError), transaction.atomic():
            EntityCountHistogram.objects.create(
                model=entity.model,
                entity_index=entity.entity_index,
                is_supertype=entity.is_supertype,
                count=999,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PsetCountHistogram.objects.create(
                model=pset.model,
                entity_index=pset.entity_index,
                pset_name=pset.pset_name,
                is_standardized=pset.is_standardized,
                count=999,
            )

    def test_scheduler_uses_completion_markers_instead_of_data_rows(self):
        model = Model.objects.create(
            file_name="pending.ifc",
            file="pending.ifc",
            size=1,
            schema="IFC4",
            uploaded_by=self.user,
        )
        TemplateStatistic.objects.bulk_create([
            TemplateStatistic(
                model=completed_model,
                template_name=template_name,
                graph=None,
            )
            for completed_model in (self.first, self.second)
            for template_name in ("First.md", "Second.md")
        ])
        task_module = "apps.ifc_validation.tasks.statistics_tasks"
        with (
            patch(f"{task_module}.psutil.cpu_percent", return_value=0),
            patch(
                f"{task_module}.available_template_names",
                return_value=("First.md", "Second.md"),
            ),
            patch(f"{task_module}.group") as task_group,
        ):
            assert schedule_model_statistic_tasks.run(batch_size=10) == 3
            task_group.return_value.apply_async.assert_called_once_with()

            task_group.reset_mock()
            EntityCountHistogram.completion_marker(model).save()
            PsetCountHistogram.completion_marker(model).save()
            assert schedule_model_statistic_tasks.run(batch_size=10) == 1

            task_group.reset_mock()
            TemplateStatistic.objects.create(
                model=model,
                template_name="First.md",
                graph=None,
            )
            assert schedule_model_statistic_tasks.run(batch_size=10) == 1
            task_group.return_value.apply_async.assert_called_once_with()

            task_group.reset_mock()
            TemplateStatistic.objects.create(
                model=model,
                template_name="Second.md",
                graph=None,
            )
            assert schedule_model_statistic_tasks.run(batch_size=10) == 0
            task_group.assert_not_called()

    def test_template_task_replaces_selected_templates_and_marks_each_one(self):
        model = Model.objects.create(
            file_name="templates.ifc",
            file="templates.ifc",
            size=1,
            schema="IFC4",
            uploaded_by=self.user,
        )
        task_module = "apps.ifc_validation.tasks.statistics_tasks"
        extracted_result = {
            "template": "First.md",
            "focus_step_id": 42,
            "focus_ifc_type": "IfcWall",
            "graph": {"PropertyType": "IfcPropertySingleValue"},
        }
        with (
            patch(
                f"{task_module}.extract_template_statistics_in_subprocess",
                return_value=[extracted_result],
            ) as extract,
            patch(
                f"{task_module}.get_absolute_file_path",
                return_value="templates.ifc",
            ),
        ):
            assert populate_template_statistics.run(
                model.pk,
                ("First.md", "Second.md"),
            ) == 1
            assert populate_template_statistics.run(
                model.pk,
                ("First.md", "Second.md"),
            ) == 1

            markers = model.template_statistics.filter(graph__isnull=True)
            assert set(markers.values_list("template_name", flat=True)) == {
                "First.md",
                "Second.md",
            }
            assert all(marker.is_completion_marker for marker in markers)
            assert "First.md statistics completed" in str(
                markers.get(template_name="First.md"),
            )
            assert model.template_statistics.get(
                graph__isnull=False,
            ).graph == extracted_result["graph"]
            extract.assert_called_with(
                "templates.ifc",
                ("First.md", "Second.md"),
            )

            extract.return_value = []
            assert populate_template_statistics.run(
                model.pk,
                ("Third.md",),
            ) == 0
            assert model.template_statistics.filter(
                template_name="Third.md",
                graph__isnull=True,
            ).exists()
            assert extract.call_args.args == ("templates.ifc", ("Third.md",))

    def test_management_command_treats_markers_as_completed(self):
        stdout = StringIO()

        call_command("populate_statistics", 1, stdout=stdout)

        assert "Processed 0 model(s)" in stdout.getvalue()

    def test_management_command_processes_a_missing_template_marker(self):
        model = Model.objects.create(
            file_name="new-template.ifc",
            file="new-template.ifc",
            size=1,
            schema="IFC4",
            uploaded_by=self.user,
        )
        EntityCountHistogram.completion_marker(model).save()
        PsetCountHistogram.completion_marker(model).save()
        template_names = available_template_names()
        TemplateStatistic.objects.bulk_create([
            TemplateStatistic(
                model=model,
                template_name=template_name,
                graph=None,
            )
            for template_name in template_names[:-1]
        ])
        stdout = StringIO()
        task_module = "apps.ifc_validation.tasks.statistics_tasks"

        with (
            patch(
                f"{task_module}.extract_template_statistics_in_subprocess",
                return_value=[],
            ),
            patch(
                f"{task_module}.get_absolute_file_path",
                return_value="new-template.ifc",
            ),
        ):
            call_command("populate_statistics", 1, stdout=stdout)

        assert "Processed 1 model(s)" in stdout.getvalue()
        assert model.template_statistics.filter(
            template_name=template_names[-1],
            graph__isnull=True,
        ).exists()

    def test_top_element_subtypes_for_model(self):
        result = self.execute(filters=[
            self.clause("model", "eq", self.first.pk),
            self.clause("entity", "subtype_of", "IfcElement"),
            self.clause("entity_kind", "eq", "concrete", False),
        ])

        assert result.columns == ["Schema", "Entity", "count"]
        assert result.rows == [
            ["IFC4", "IfcWall", 10],
            ["IFC4", "IfcDoor", 5],
            ["IFC4", "IfcBuildingElementProxy", 2],
        ]

    def test_average_entity_counts_and_number_of_models(self):
        average = self.execute(
            expression="avg(count)",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("entity", "subtype_of", "IfcElement"),
                self.clause("entity_kind", "eq", "concrete", False),
            ],
        )
        model_count = self.execute(
            expression="models",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("entity", "eq", "IfcWall"),
                self.clause("count", "gt", 0),
            ],
        )

        assert average.rows[0] == ["IFC4", "IfcWall", 20]
        assert model_count.rows == [["IFC4", "IfcWall", 2]]

    def test_explicit_division_by_computed_models(self):
        result = self.execute(
            expression="count / computed_models",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("entity", "eq", "IfcWall"),
                self.clause("entity_kind", "eq", "concrete", False),
            ],
        )

        assert result.rows == [["IFC4", "IfcWall", 20]]

    def test_property_set_ratio_and_average_ratio(self):
        one_model = self.execute(
            source="pset",
            group_by="standardized",
            expression="count / total_count",
            filters=[
                self.clause("model", "eq", self.first.pk),
                self.clause("pset_scope", "eq", "definitions", True),
            ],
        )
        schema_average = self.execute(
            source="pset",
            group_by="standardized",
            expression="avg(count / model_total_count)",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("pset_scope", "eq", "definitions", True),
            ],
        )

        assert one_model.rows == [["Standard", .8], ["Custom", .2]]
        assert dict(schema_average.rows) == {"Standard": .5, "Custom": .5}

    def test_proxy_ratio_uses_filtered_element_total(self):
        result = self.execute(
            group_by="proxy",
            expression="count / total_count",
            filters=[
                self.clause("model", "eq", self.first.pk),
                self.clause("entity", "subtype_of", "IfcElement"),
                self.clause("entity_kind", "eq", "concrete", False),
            ],
        )

        assert result.rows[0][0] == "Other element subtypes"
        self.assertAlmostEqual(result.rows[0][1], 15 / 17)
        assert result.rows[1][0] == "Proxy"
        self.assertAlmostEqual(result.rows[1][1], 2 / 17)

    def test_entity_origin_and_negated_subtype_filters(self):
        inherited = self.execute(filters=[
            self.clause("model", "eq", self.first.pk),
            self.clause("entity_kind", "eq", "inherited", True),
        ])
        outside_elements = self.execute(filters=[
            self.clause("model", "eq", self.first.pk),
            self.clause("entity", "not_subtype_of", "IfcElement"),
            self.clause("entity_kind", "eq", "concrete", False),
        ])

        assert inherited.rows == [["IFC4", "IfcElement", 17]]
        assert outside_elements.rows == [["IFC4", "IfcProject", 1]]

    def test_ordering_and_limit_apply_to_selected_value(self):
        result = self.execute(
            ordering="ascending",
            limit=2,
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("entity_kind", "eq", "concrete", False),
            ],
        )

        assert result.rows == [
            ["IFC4", "IfcProject", 1],
            ["IFC4", "IfcBuildingElementProxy", 2],
        ]

    def test_property_set_totals_by_name_and_associated_entity(self):
        definitions = self.execute(
            source="pset",
            group_by="pset",
            filters=[
                self.clause("model", "eq", self.first.pk),
                self.clause("pset_scope", "eq", "definitions", True),
            ],
        )
        associations = self.execute(
            source="pset",
            group_by="entity",
            filters=[
                self.clause("model", "eq", self.first.pk),
                self.clause("pset_scope", "eq", "associations", False),
            ],
        )

        assert definitions.rows == [
            ["Pset_WallCommon", 8],
            ["Custom_First", 2],
        ]
        assert associations.rows == [
            ["IFC4", "IfcWall", 8],
            ["IFC4", "IfcDoor", 2],
        ]

    def test_property_set_text_and_standardization_filters(self):
        standard_wall_sets = self.execute(
            source="pset",
            group_by="pset",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("pset_scope", "eq", "definitions", True),
                self.clause("pset_name", "contains", "wall"),
                self.clause("standardized", "eq", "standard", True),
            ],
        )
        custom_sets = self.execute(
            source="pset",
            group_by="pset",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("pset_scope", "eq", "definitions", True),
                self.clause("standardized", "eq", "custom", False),
            ],
        )

        assert standard_wall_sets.rows == [["Pset_WallCommon", 10]]
        assert custom_sets.rows == [["Custom_Second", 8], ["Custom_First", 2]]

    def test_template_statistics_have_meaningful_groups_and_expressions(self):
        totals = self.execute(
            source="template",
            group_by="template",
            filters=[self.clause("schema", "eq", "IFC4")],
        )
        model_counts = self.execute(
            source="template",
            group_by="template",
            expression="models",
            filters=[self.clause("schema", "eq", "IFC4")],
        )
        focus_percentages = self.execute(
            source="template",
            group_by="entity",
            expression="count / total_count",
            filters=[self.clause("schema", "eq", "IFC4")],
        )
        name_filter = self.execute(
            source="template",
            group_by="template",
            filters=[
                self.clause("schema", "eq", "IFC4"),
                self.clause("template", "not_contains", "Template_B"),
            ],
        )

        assert totals.rows == [["Template_A.md", 3], ["Template_B.md", 1]]
        assert model_counts.rows == [["Template_A.md", 2], ["Template_B.md", 1]]
        assert focus_percentages.rows == [["IfcWall", .75], ["IfcDoor", .25]]
        assert name_filter.rows == [["Template_A.md", 3]]

    def test_template_graph_values_can_be_grouped_with_authoring_tool(self):
        tool = AuthoringTool.objects.create(name="Example CAD", version="2026")
        self.first.produced_by = tool
        self.first.save(update_fields=["produced_by"])
        TemplateStatistic.objects.bulk_create([
            TemplateStatistic(
                model=self.first,
                template_name="Use_of_property_types.md",
                graph={"PropertyType": "IfcPropertySingleValue"},
            ),
            TemplateStatistic(
                model=self.first,
                template_name="Use_of_property_types.md",
                graph={"PropertyType": "IfcPropertySingleValue"},
            ),
            TemplateStatistic(
                model=self.first,
                template_name="Use_of_property_types.md",
                graph={"PropertyType": "IfcPropertyEnumeratedValue"},
            ),
        ])

        result = self.execute(
            source="template",
            group_by=["authoring_tool", "graph_value:PropertyType"],
            filters=[self.clause(
                "template", "eq", "Use_of_property_types.md",
            )],
            limit=None,
        )

        assert result.columns == [
            "Authoring tool ID",
            "Authoring tool",
            "Version",
            "Graph: PropertyType",
            "count",
        ]
        assert result.rows == [
            [tool.pk, "Example CAD", "2026", "IfcPropertySingleValue", 2],
            [tool.pk, "Example CAD", "2026", "IfcPropertyEnumeratedValue", 1],
        ]
        assert "->>" in result.sql or "#>>" in result.sql

    def test_template_graph_value_supports_a_single_model_basis_query(self):
        TemplateStatistic.objects.bulk_create([
            TemplateStatistic(
                model=self.first,
                template_name="Usage_of_transition_curves_geometry.md",
                graph={"ParentCurve": "IfcClothoid"},
            ),
            TemplateStatistic(
                model=self.first,
                template_name="Usage_of_transition_curves_geometry.md",
                graph={"ParentCurve": "IfcClothoid"},
            ),
            TemplateStatistic(
                model=self.first,
                template_name="Usage_of_transition_curves_geometry.md",
                graph={"ParentCurve": "IfcPolynomialCurve"},
            ),
        ])

        result = self.execute(
            source="template",
            group_by="graph_value:ParentCurve",
            filters=[
                self.clause("model", "eq", self.first.pk),
                self.clause(
                    "template", "eq", "Usage_of_transition_curves_geometry.md",
                ),
            ],
            limit=None,
        )

        assert result.columns == ["Graph: ParentCurve", "count"]
        assert result.rows == [["IfcClothoid", 2], ["IfcPolynomialCurve", 1]]

    def test_template_graph_value_supports_reusable_nested_paths(self):
        TemplateStatistic.objects.create(
            model=self.first,
            template_name="Nested.md",
            graph={"Property": {"Type": "IfcPropertyListValue"}},
        )

        result = self.execute(
            source="template",
            group_by="graph_value:Property.Type",
            filters=[self.clause("template", "eq", "Nested.md")],
        )

        assert result.columns == ["Graph: Property.Type", "count"]
        assert result.rows == [["IfcPropertyListValue", 1]]
        assert "#>>" in result.sql

    def test_incompatible_compositions_raise_from_query_builder(self):
        with self.assertRaisesRegex(ValueError, "not available"):
            self.execute(
                source="template",
                group_by="template",
                filters=[self.clause("count", "gt", 0)],
            )
        with self.assertRaisesRegex(ValueError, "one model or one exact schema"):
            self.execute(
                filters=[self.clause("entity", "eq", "IfcWall")],
            )
        with self.assertRaisesRegex(ValueError, "Proxy grouping requires"):
            self.execute(group_by="proxy", filters=[])

    def test_minimal_query_renders_schema_and_entity_cells(self):
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(),
        ])

        assert response.status_code == 200
        assert response.context["rows"][0] == ["IFC4", "IfcElement", 52]
        assert b"<td>IFC4</td>" in response.content
        assert b"<td>IfcElement</td>" in response.content
        assert b"<td>52</td>" in response.content
        assert b'id="statistics-copy-results"' in response.content
        assert b"Copy results for Excel" in response.content
        assert b"tableToTsv" in response.content
        assert "\nFROM " in response.context["sql"]

    def test_model_admin_histogram_links_target_statistics_queries(self):
        model_admin = django_admin.site._registry[Model]

        entity_link = str(model_admin.histogram_link(self.first))
        pset_link = str(model_admin.pset_histogram_link(self.first))

        assert "/model/statistics/?source=entity&amp;model=" in entity_link
        assert "/model/statistics/?source=pset&amp;model=" in pset_link
        assert "/histogram/" not in entity_link
        assert "/pset-histogram/" not in pset_link
        for removed_url_name in (
            "admin:ifc_validation_models_model_histograms",
            "admin:ifc_validation_models_model_pset_histograms",
            "admin:ifc_validation_models_model_histogram",
            "admin:ifc_validation_models_model_pset_histogram",
        ):
            with self.assertRaises(NoReverseMatch):
                reverse(removed_url_name)

    def test_entity_histogram_statistics_link_executes_equivalent_query(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin:ifc_validation_models_model_statistics"),
            {"source": "entity", "model": self.first.pk},
        )

        assert response.status_code == 200
        assert response.context["query_error"] == ""
        assert response.context["clause_formset"].is_valid()
        assert response.context["clause_formset"].forms[-1].cleaned_data[
            "resolved_value"
        ] is None
        assert {
            row[1]: row[-1]
            for row in response.context["rows"]
        } == self.first.get_histogram(include_supertypes=True)

    def test_pset_histogram_statistics_link_executes_equivalent_query(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin:ifc_validation_models_model_statistics"),
            {"source": "pset", "model": self.first.pk},
        )

        expected = {
            (
                entry.entity_name,
                entry.pset_name or "(unnamed)",
                "Standard" if entry.is_standardized else "Custom",
            ): entry.count
            for entry in self.first.pset_count_entries.filter(count__gt=0)
        }
        assert response.status_code == 200
        assert response.context["query_error"] == ""
        assert response.context["clause_formset"].is_valid()
        assert response.context["clause_formset"].forms[-1].cleaned_data[
            "resolved_value"
        ] is None
        assert response.context["columns"] == [
            "Schema", "Entity", "Property set", "Standardized", "count",
        ]
        assert {
            (row[1], row[2], row[3]): row[-1]
            for row in response.context["rows"]
        } == expected

    def test_expression_ui_renders_only_structured_dropdowns(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("admin:ifc_validation_models_model_statistics"),
        )

        assert response.status_code == 200
        for field in (
            "expression_function",
            "operand_a",
            "expression_operator",
            "operand_b",
        ):
            assert f'name="clauses-__prefix__-{field}"'.encode() in response.content
        assert b"statistics-expression-values" not in response.content
        assert b"statistics-example-clause" in response.content
        assert b"Top 10 element subtypes used in one file" in response.content
        assert b"Average proxy ratio in files of an IFC version" in response.content
        assert response.content.count(b"data-example-index=") == 13
        assert b'id="statistics-query-examples"' in response.content

    def test_source_controls_available_filter_and_group_choices(self):
        context = statistics_query_ui_context()

        entity_filters = {
            choice["value"] for choice in context["clause_target_choices"]["filter"]["entity"]
        }
        pset_filters = {
            choice["value"] for choice in context["clause_target_choices"]["filter"]["pset"]
        }
        template_filters = {
            choice["value"]
            for choice in context["clause_target_choices"]["filter"]["template"]
        }
        template_groups = {
            choice["value"] for choice in context["clause_target_choices"]["group"]["template"]
        }
        assert "filter:pset_name" not in entity_filters
        assert "filter:pset_name" in pset_filters
        assert "filter:count" not in template_filters
        assert "group:template" in template_groups
        assert "group:authoring_tool" in template_groups
        assert "group:graph_value" in template_groups

    def test_all_requested_example_query_patterns_are_available(self):
        examples = statistics_query_ui_context()["statistics_query_examples"]

        assert [example["title"] for example in examples] == [
            "Top 10 element subtypes used in one file",
            "Average top 10 element subtypes used in files of an IFC version",
            "Number of files of an IFC version containing an entity",
            "Top 10 property sets used in one file",
            "Average top 10 property sets used in files of an IFC version",
            "Ratio of standard versus custom property sets in one file",
            "Average ratio of standard versus custom property sets by IFC version",
            "Ratio of proxy versus other element subtypes in one file",
            "Average proxy ratio in files of an IFC version",
            "Property type counts grouped by AuthoringTool",
            "Property type counts for a single model",
            "Basis counts grouped by AuthoringTool",
            "Basis type counts for a single model",
        ]
        for example in examples:
            operations = [clause["operation"] for clause in example["clauses"]]
            assert operations.count("Group by") >= 1
            assert operations.count("Expression") == 1

        expressions = [
            next(clause for clause in example["clauses"] if clause["operation"] == "Expression")
            for example in examples
        ]
        assert expressions[5]["expression"] == {
            "function": "𝑓",
            "function_active": False,
            "operand_a": "count",
            "operator": "÷",
            "operator_active": True,
            "operand_b": "total count",
            "operand_b_active": True,
        }
        assert expressions[6]["expression"]["function"] == "AVG"
        assert expressions[6]["expression"]["operand_b"] == (
            "model total count"
        )

    def test_every_example_payload_executes_through_the_admin_builder(self):
        tool = AuthoringTool.objects.create(name="Example CAD", version="2026")
        self.first.produced_by = tool
        self.first.save(update_fields=["produced_by"])
        TemplateStatistic.objects.bulk_create([
            TemplateStatistic(
                model=self.first,
                template_name="Use_of_property_types.md",
                graph={"PropertyType": "IfcPropertySingleValue"},
            ),
            TemplateStatistic(
                model=self.first,
                template_name="Usage_of_transition_curves_geometry.md",
                graph={"ParentCurve": "IfcClothoid"},
            ),
        ])
        examples = statistics_query_ui_context()["statistics_query_examples"]

        for example in examples:
            with self.subTest(example=example["title"]):
                form_data = example["form_data"]
                clauses = [clause.copy() for clause in form_data["clauses"]]
                for clause in clauses:
                    if clause.get("target") == "filter:model":
                        clause["value"] = self.first.pk
                response = self.post_query(clauses, source=form_data["source"])

                assert response.status_code == 200
                assert response.context["clause_formset"].is_valid()
                assert response.context["query_error"] == ""
                assert response.context["rows"]

    def test_order_and_limit_clauses_are_built_from_admin_formset(self):
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(function="sum"),
            {"operation": "order", "target": "order:ascending"},
            {"operation": "limit", "value": 2},
            {
                "operation": "filter",
                "target": "filter:entity_kind",
                "operator": "eq",
                "value": "concrete",
            },
        ])

        assert response.status_code == 200
        assert response.context["rows"] == [
            ["IFC4", "IfcProject", 1],
            ["IFC4", "IfcBuildingElementProxy", 2],
        ]

    def test_admin_post_builds_result_without_persisting_a_report(self):
        before = EntityCountHistogram.objects.count()
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(),
            {
                "operation": "filter",
                "target": "filter:model",
                "operator": "eq",
                "value": self.first.pk,
            },
            {
                "operation": "filter",
                "target": "filter:entity",
                "operator": "subtype_of",
                "value": "IfcElement",
            },
            {
                "operation": "filter",
                "target": "filter:entity_kind",
                "operator": "eq",
                "value": "concrete",
            },
        ])

        assert response.status_code == 200
        assert response.context["rows"][0] == ["IFC4", "IfcWall", 10]
        assert b"<td>IFC4</td>" in response.content
        assert b"<td>IfcWall</td>" in response.content
        assert "SELECT" in response.context["sql"]
        assert EntityCountHistogram.objects.count() == before

    def test_repeated_count_filters_form_a_range(self):
        result = self.execute(filters=[
            self.clause("model", "eq", self.first.pk),
            self.clause("count", "gt", 4),
            self.clause("count", "lt", 10),
        ])

        assert result.rows == [["IFC4", "IfcDoor", 5]]

    def test_admin_formset_accepts_repeated_count_filters(self):
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(),
            {
                "operation": "filter",
                "target": "filter:model",
                "operator": "eq",
                "value": self.first.pk,
            },
            {
                "operation": "filter",
                "target": "filter:count",
                "operator": "gt",
                "value": 4,
            },
            {
                "operation": "filter",
                "target": "filter:count",
                "operator": "lt",
                "value": 10,
            },
        ])

        assert response.status_code == 200
        assert response.context["rows"] == [["IFC4", "IfcDoor", 5]]

    def test_admin_expression_clause_accepts_explicit_division(self):
        response = self.post_query(
            [
                {"operation": "group", "target": "group:standardized"},
                self.expression(
                    operand_a="count",
                    operator="divide",
                    operand_b="total_count",
                ),
                {
                    "operation": "filter",
                    "target": "filter:model",
                    "operator": "eq",
                    "value": self.first.pk,
                },
                {
                    "operation": "filter",
                    "target": "filter:pset_scope",
                    "operator": "eq",
                    "value": "definitions",
                },
            ],
            source="pset",
        )

        assert response.status_code == 200
        assert response.context["rows"] == [["Standard", 0.8], ["Custom", 0.2]]

    def test_admin_expression_supports_function_of_binary_operands(self):
        response = self.post_query(
            [
                {"operation": "group", "target": "group:standardized"},
                self.expression(
                    function="average",
                    operand_a="count",
                    operator="divide",
                    operand_b="model_total_count",
                ),
                {
                    "operation": "filter",
                    "target": "filter:schema",
                    "operator": "eq",
                    "value": "IFC4",
                },
                {
                    "operation": "filter",
                    "target": "filter:pset_scope",
                    "operator": "eq",
                    "value": "definitions",
                },
            ],
            source="pset",
        )

        assert response.status_code == 200
        assert dict(response.context["rows"]) == {"Standard": 0.5, "Custom": 0.5}

    def test_invalid_function_combination_is_reported_as_query_error(self):
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(function="sum", operand_a="model"),
        ])

        assert response.status_code == 200
        assert "Unsupported SUM expression" in response.context["query_error"]

    def test_invalid_composition_is_reported_by_backend_builder(self):
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(),
            self.expression(function="count_distinct", operand_a="model"),
        ])

        assert response.status_code == 200
        assert response.context["clause_formset"].is_valid()
        assert response.context["query_error"] == (
            "The query requires exactly one expression clause."
        )

    def test_removed_clause_is_ignored_when_the_form_is_submitted(self):
        response = self.post_query([
            {"operation": "group", "target": "group:entity"},
            self.expression(),
            {
                **self.expression(function="count_distinct", operand_a="model"),
                "DELETE": "on",
            },
        ])

        assert response.status_code == 200
        assert response.context["query_error"] == ""
        assert response.context["rows"][0] == ["IFC4", "IfcElement", 52]

    def test_all_supported_group_and_expression_combinations_execute(self):
        expressions = (
            "count",
            "avg(count)",
            "models",
            "count / total_count",
            "avg(count / model_total_count)",
        )

        for source in SOURCES:
            groups = [
                concept.name for concept in CONCEPTS
                if concept.supports("group", source.name)
            ]
            for group in groups:
                for expression in expressions:
                    with self.subTest(source=source.name, group=group, expression=expression):
                        resolved_group = (
                            "graph_value:value" if group == "graph_value" else group
                        )
                        result = self.execute(
                            source=source.name,
                            group_by=resolved_group,
                            expression=expression,
                        )
                        assert result.columns
                        assert result.rows
                        assert all(
                            value not in (None, "")
                            for row in result.rows
                            for value in row[:-1]
                        )
