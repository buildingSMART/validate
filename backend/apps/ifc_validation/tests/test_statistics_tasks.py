from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
import ifcopenshell

from apps.ifc_validation_models.models import (
    EntityCountHistogram,
    ValidationRequest,
    set_user_context,
)

from ..statistics_query import StatisticsQueryBuilder
from ..statistics_query_concepts import (
    QueryFilter,
    StatisticsAnnotation,
    StatisticsExpression,
    StatisticsQuery,
)
from ..tasks.statistics_tasks import populate_entity_count_histogram
from ..tasks.utils import get_absolute_file_path, get_or_create_ifc_model


class PopulateEntityCountHistogramTestCase(TransactionTestCase):

    @staticmethod
    def set_user_context():
        user, _ = User.objects.get_or_create(
            id=1,
            defaults={
                "username": "SYSTEM",
                "is_active": True,
            },
        )
        set_user_context(user)

    def test_populate_entity_count_histogram(self):
        self.set_user_context()
        cases = ((0, 1), (1, 0), (1, 1))

        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root,
        ), patch(
            "apps.ifc_validation.tasks.utils.MEDIA_ROOT",
            media_root,
        ):
            get_absolute_file_path.cache_clear()
            try:
                for wall_count, proxy_count in cases:
                    ifc_file = ifcopenshell.file(schema="IFC4")
                    for _ in range(wall_count):
                        ifc_file.create_entity("IfcWall")
                    for _ in range(proxy_count):
                        ifc_file.create_entity("IfcBuildingElementProxy")

                    file_name = f"walls-{wall_count}-proxies-{proxy_count}.ifc"
                    file_path = Path(media_root) / file_name
                    ifc_file.write(str(file_path))

                    request = ValidationRequest.objects.create(
                        file_name=file_name,
                        file=file_name,
                        size=file_path.stat().st_size,
                    )
                    request.mark_as_initiated()
                    model = get_or_create_ifc_model(request.id)
                    model.schema = ifc_file.schema_identifier
                    model.save(update_fields=("schema",))

                    populated_count = populate_entity_count_histogram(model.id)
                    entries = EntityCountHistogram.objects.filter(model=model)

                    self.assertEqual(
                        populated_count,
                        entries.filter(count__gt=0).count(),
                    )
                    self.assertEqual(entries.filter(count=0).count(), 1)

                    concrete_counts = {
                        entry.entity_name: entry.count
                        for entry in entries.filter(
                            count__gt=0,
                            is_supertype=False,
                        )
                    }
                    expected_concrete_counts = {
                        entity_name: count
                        for entity_name, count in (
                            ("IfcWall", wall_count),
                            ("IfcBuildingElementProxy", proxy_count),
                        )
                        if count
                    }
                    self.assertEqual(
                        concrete_counts,
                        expected_concrete_counts,
                    )

                    for entity_name in ("IfcBuildingElement", "IfcElement"):
                        inherited_entry = entries.get(
                            entity_index=EntityCountHistogram.index_from_string(
                                model.schema,
                                entity_name,
                            ),
                            is_supertype=True,
                        )
                        self.assertEqual(
                            inherited_entry.count,
                            wall_count + proxy_count,
                        )

                    query = StatisticsQuery(
                        source="entity",
                        groups=(),
                        expression=StatisticsExpression(
                            operand_a="proxy_count",
                            operator="divide",
                            operand_b="building_element_count",
                        ),
                        filters=(
                            QueryFilter("model", "eq", model.id),
                        ),
                        annotations=(
                            StatisticsAnnotation(
                                "proxy_count",
                                filters=(QueryFilter(
                                    "entity",
                                    "eq",
                                    "IfcBuildingElementProxy",
                                ),),
                            ),
                            StatisticsAnnotation(
                                "building_element_count",
                                filters=(QueryFilter(
                                    "entity",
                                    "eq",
                                    "IfcBuildingElement",
                                ),),
                            ),
                        ),
                    )
                    ratio_result = StatisticsQueryBuilder(query).execute()
                    total = wall_count + proxy_count
                    self.assertEqual(
                        ratio_result.columns,
                        ["proxy_count / building_element_count"],
                    )
                    self.assertAlmostEqual(
                        ratio_result.rows[0][0],
                        proxy_count / total,
                    )
            finally:
                get_absolute_file_path.cache_clear()
