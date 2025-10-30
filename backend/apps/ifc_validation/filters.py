from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from core.filters import AdvancedInputFilter


class ModelProducedByAdvancedFilter(AdvancedInputFilter):

    parameter_name = 'model__produced_by__contains'
    title = _('Produced By')

    def queryset(self, request, queryset):

        term = self.value()

        if term is None:
            return

        any_name = Q()
        for bit in term.split():
            any_name &= (
                Q(model__produced_by__name__icontains=bit) |
                Q(model__produced_by__version__icontains=bit) |
                Q(model__produced_by__company__name__icontains=bit)
            )

        return queryset.filter(any_name)
    

class ProducedByAdvancedFilter(AdvancedInputFilter):

    parameter_name = 'produced_by__contains'
    title = _('Produced By')

    def queryset(self, request, queryset):

        term = self.value()

        if term is None:
            return

        any_name = Q()
        for bit in term.split():
            any_name &= (
                Q(produced_by__name__icontains=bit) |
                Q(produced_by__version__icontains=bit) |
                Q(produced_by__company__name__icontains=bit)
            )

        return queryset.filter(any_name)
    

class CreatedByAdvancedFilter(AdvancedInputFilter):

    parameter_name = 'created_by__contains'
    title = _('Created By')

    def queryset(self, request, queryset):

        term = self.value()

        if term is None:
            return

        any = Q()
        for bit in term.split():
            any &= (
                Q(created_by__username=bit) |
                Q(created_by__last_name__icontains=bit) |
                Q(created_by__first_name__icontains=bit)
            )

        return queryset.filter(any)