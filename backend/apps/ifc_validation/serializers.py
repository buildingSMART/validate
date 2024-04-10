from rest_framework import serializers

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import ValidationOutcome


class BaseSerializer(serializers.HyperlinkedModelSerializer):

    def get_field_names(self, declared_fields, info):

        # Django does not support both 'fields' and 'exclude'

        expanded_fields = super(BaseSerializer, self).get_field_names(declared_fields, info)

        if getattr(self.Meta, 'show', None):
            expanded_fields = expanded_fields + self.Meta.show

        if getattr(self.Meta, 'hide', None):
            expanded_fields = list(set(expanded_fields) - set(self.Meta.hide))
        
        return expanded_fields
        

class ValidationRequestSerializer(BaseSerializer):
    
    class Meta:
        model = ValidationRequest
        fields = '__all__'
        show = ["public_id", "model_public_id"]
        hide = ["id", "model"]


class ValidationTaskSerializer(BaseSerializer):

    class Meta:
        model = ValidationTask
        fields = '__all__'
        show = ["public_id", "request_public_id"]
        hide = ["id", "process_id", "process_cmd", "request"]


class ValidationOutcomeSerializer(BaseSerializer):

    class Meta:
        model = ValidationOutcome
        fields = '__all__'
        show = ["public_id", "instance_public_id", "validation_task_public_id"]
        hide = ["id", "instance", "validation_task"]
