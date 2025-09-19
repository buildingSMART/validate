from rest_framework import serializers

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import ValidationOutcome
from apps.ifc_validation_models.models import Model


class BaseSerializer(serializers.ModelSerializer):

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
        hide = ["id", "model", "deleted", "created_by", "updated_by"]
        read_only_fields = ['size', 'created_by', 'updated_by']


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


class ModelSerializer(BaseSerializer):

    class Meta:
        model = Model
        fields = '__all__'
        show = ["public_id"]
        hide = ["id", "number_of_elements", "number_of_geometries", "number_of_properties"] # no longer used
        read_only_fields = ['',]