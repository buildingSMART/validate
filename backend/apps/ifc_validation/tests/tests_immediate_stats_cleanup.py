"""Regression tests for the IMMEDIATE_STATS_AND_CLEANUP foreground workflow."""
from unittest import mock

from django.test import SimpleTestCase

from apps.ifc_validation.tasks import statistics_tasks


class ImmediateStatsChordBodyTestCase(SimpleTestCase):
    """`populate_model_statistics` is the first element of `final_tasks`, and
    `final_tasks` becomes the body of the parallel chord. Celery invokes a chord
    body with the chord's result list as a positional argument, so the task has
    to tolerate that alongside its id/file_name keywords.

    Regression: the task used to be declared `(self, id, *args, **kwargs)`.
    As soon as the parallel stage finished, the result backend's
    `trigger_callback` called `callback.delay(ret)` and raised
    "TypeError: populate_model_statistics() got multiple values for argument
    'id'". Because that happens outside a task context the error callback never
    fired, so nothing was marked as failed: requests just stopped at
    progress=75 forever and `remove_validated_file` never ran, leaving every
    uploaded file on disk.
    """

    def test_accepts_chord_result_list_as_positional_argument(self):
        with mock.patch.object(statistics_tasks, "ValidationRequest") as request_cls:
            # a request without a model short-circuits the task
            request_cls.objects.get.return_value = mock.Mock(model=None)

            result = statistics_tasks.populate_model_statistics.apply(
                # exactly what Celery passes to a chord body
                args=([{"status": "ok"}],),
                kwargs={"id": 1, "file_name": "valid_file.ifc"},
            )

        self.assertEqual(result.get(), 0)

    def test_missing_id_is_reported(self):
        result = statistics_tasks.populate_model_statistics.apply(kwargs={})
        self.assertRaises(ValueError, result.get)
