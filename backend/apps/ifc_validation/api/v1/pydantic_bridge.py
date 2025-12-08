from rest_framework import serializers
from pydantic import ValidationError as PydanticValidationError

class PydanticValidatorMixin:
    """
    Bridge for Pydantic & DRF. Set `Schema` on subclasses.

    """
    Schema = None 

    # allow subclasses to filter which keys from Pydantic we keep
    _pydantic_keep_keys: set[str] | None = None

    def validate(self, attrs):
        if self.Schema is None:
            return attrs
        try:
            model = self.Schema.model_validate(attrs)
        except PydanticValidationError as exc:
            err_map = {}
            for err in exc.errors():
                loc = err.get("loc", ())
                field = "non_field_errors"
                if loc and loc[0] != "__root__":
                    field = ".".join(map(str, loc))
                msg = err.get("msg", "")
                if msg.lower().startswith("value error, "):
                    msg = msg[len("Value error, "):]
                err_map.setdefault(field, []).append(msg)
            raise serializers.ValidationError(err_map)

        normalized = model.model_dump()

        normalized.pop("files", None)

        if self._pydantic_keep_keys is not None:
            normalized = {k: v for k, v in normalized.items() if k in self._pydantic_keep_keys}

        return {**attrs, **normalized}
