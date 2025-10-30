import datetime
from django.utils import timezone

from django.db import models
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

class AdvancedDateFilter(admin.DateFieldListFilter):

    def __init__(self, field, request, params, model, model_admin, field_path):

        super().__init__(field, request, params, model, model_admin, field_path)

        now = timezone.now()
        # When time zone support is enabled, convert "now" to the user's time
        # zone so Django's definition of "Today" matches what the user expects.
        if timezone.is_aware(now):
            now = timezone.localtime(now)

        if isinstance(field, models.DateTimeField):
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:  # field is a models.DateField
            today = now.date()
        tomorrow = today + datetime.timedelta(days=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        next_year = today.replace(year=today.year + 1, month=1, day=1)

        self.lookup_kwarg_since = "%s__gte" % field_path
        self.lookup_kwarg_until = "%s__lt" % field_path
        self.links = (
            (_("Any date"), {}),
            (
                _("Today"),
                {
                    self.lookup_kwarg_since: today,
                    self.lookup_kwarg_until: tomorrow,
                },
            ),
            (
                _("Yesterday"),
                {
                    self.lookup_kwarg_since: today - datetime.timedelta(days=1),
                    self.lookup_kwarg_until: today - datetime.timedelta(days=1),
                },
            ),
            (
                _("Past 7 days"),
                {
                    self.lookup_kwarg_since: today - datetime.timedelta(days=7),
                    self.lookup_kwarg_until: tomorrow,
                },
            ),
            (
                _("This month"),
                {
                    self.lookup_kwarg_since: today.replace(day=1),
                    self.lookup_kwarg_until: next_month,
                },
            ),
            (
                _("Last month"),
                {
                    self.lookup_kwarg_since: (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1),
                    self.lookup_kwarg_until: today.replace(day=1) - datetime.timedelta(days=1),
                },
            ),
            (
                _("This year"),
                {
                    self.lookup_kwarg_since: today.replace(month=1, day=1),
                    self.lookup_kwarg_until: next_year,
                },
            ),
        )
        
        if field.null:
            self.lookup_kwarg_isnull = "%s__isnull" % field_path
            self.links += (
                (_("No date"), {self.field_generic + "isnull": True}),
                (_("Has date"), {self.field_generic + "isnull": False}),
            )


class AdvancedInputFilter(admin.SimpleListFilter):
    
    template = 'admin/advanced_input_filter.html'

    def lookups(self, request, model_admin):
        
        # required to show the filter
        return ((),)
    
    def get_facet_counts(self, pk_attname, filtered_qs):

        # not supported, return empty dict
        return {}

    def choices(self, changelist):
        
        # grab only the "all" option
        all_choice = next(super().choices(changelist))
        all_choice['query_parts'] = (
            (k, v)
            for k, v in changelist.get_filters_params().items()
            if k != self.parameter_name
        )
        yield all_choice
