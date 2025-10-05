from rest_framework import serializers

from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import ValidationOutcome
from apps.ifc_validation_models.models import Model

from core.settings import MAX_FILE_SIZE_IN_MB

class BaseSerializer(serializers.ModelSerializer):

    def get_field_names(self, declared_fields, info):

        # Django does not support both 'fields' and 'exclude'

        expanded_fields = super(BaseSerializer, self).get_field_names(declared_fields, info)

        if getattr(self.Meta, 'show', None):
            expanded_fields = expanded_fields + self.Meta.show

        if getattr(self.Meta, 'hide', None):
            expanded_fields = list(set(expanded_fields) - set(self.Meta.hide))
        
        return expanded_fields

    class Meta:
        abstract = True
        

class ValidationRequestSerializer(BaseSerializer):
    
    class Meta:
        model = ValidationRequest
        fields = '__all__'
        show = ["public_id", "model_public_id"]
        hide = ["id", "model", "deleted", "created_by", "updated_by", "status_reason"]
        read_only_fields = ['size', 'created_by', 'updated_by']

    def validate_file(self, value):

        # ensure file is not empty
        if not value:
            raise serializers.ValidationError("File is required.")
        
        # ensure size is under MAX_FILE_SIZE_IN_MB
        if value.size > MAX_FILE_SIZE_IN_MB * 1024 * 1024:
            raise serializers.ValidationError(f"File size exceeds allowed file size limit ({MAX_FILE_SIZE_IN_MB} MB).")
        
        return value
    
    def validate_files(self, value):
        
        # ensure exactly one file is uploaded
        if len(value) > 1:
            raise serializers.ValidationError({"file": "Only one file can be uploaded at a time."})
        
        return value

    def validate_file_name(self, value):

        # ensure file name is not empty
        if not value:
            raise serializers.ValidationError("File name is required.")
        
        # ensure file name ends with .ifc
        if not value.lower().endswith('.ifc'):
            raise serializers.ValidationError(f"File name must end with '.ifc'.")
        
        return value

    def validate_size(self, value):
        
        # ensure size is positive
        if value <= 0:
            raise serializers.ValidationError("Size must be positive.")
        
        # ensure size is under MAX_FILE_SIZE_IN_MB
        if value > MAX_FILE_SIZE_IN_MB * 1024 * 1024:
            raise serializers.ValidationError(f"File size exceeds allowed file size limit ({MAX_FILE_SIZE_IN_MB} MB).")
        
        return value


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