from rest_framework import serializers
from pydantic import ValidationError as PydanticValidationError

class PydanticValidatorMixin:
    """
    Bridge for Pydantic & Django DRF
    """
    Schema = None 

    def _pydantic_validate(self, attrs: dict) -> dict:
        if self.Schema is None:
            return attrs
        try:
            model = self.Schema.model_validate(attrs)
            return model.model_dump()
        except PydanticValidationError as exc:
            error_dict = {}
            for err in exc.errors():
                loc = err.get("loc", ())
                field = loc[0] if loc else serializers.NON_FIELD_ERRORS
                error_dict.setdefault(field, []).append(err.get("msg"))
            raise serializers.ValidationError(error_dict)

    def to_internal_value(self, data):
        attrs = super().to_internal_value(data) # DRF parses to to python object
        return self._pydantic_validate(attrs) # Pydantic validation
