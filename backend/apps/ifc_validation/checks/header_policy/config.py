from pydantic import BaseModel, ConfigDict

class ConfiguredBaseModel(BaseModel):
    """Base Pydantic model with assignment validation enabled.

    Serves as a base class for Pydantic models, enabling validation when instance values are changed.
    """
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True  # Allow arbitrary types like `ifcopenshell.file`
    )