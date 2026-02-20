from typing import Any, Optional
from dataclasses import dataclass
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask

@dataclass # moving context from exeuction to processing layer
class TaskContext:
    config: Any  # Static info -- hould be TaskConfig — delayed import due to modular imports
    request: ValidationRequest # the current request 
    task: ValidationTask #the current task  
    file_path: str # for IFC files             
    result: Optional[Any] = None # result from execution layer    
