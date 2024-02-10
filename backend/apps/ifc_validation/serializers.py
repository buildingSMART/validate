from rest_framework import serializers

from apps.ifc_validation_models.models import ValidationRequest, ValidationTask, ValidationOutcome


class ValidationRequestSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ValidationRequest
        read_only_fields = ("id", "size", "created", "created_by", "updated", "updated_by")
        fields = ("id", "file_name", "file", "size", "status", "status_reason", "progress", "created", "created_by", "updated", "updated_by")


class ValidationTaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = ValidationTask
        fields = '__all__'


class ValidationOutcomeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ValidationOutcome
        fields = '__all__'
