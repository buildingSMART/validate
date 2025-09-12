import os
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

    @property
    def rdb_file_path_if_exists(self):
        # fn = self.file_path + ".rdb"
        fn = "/tmp/" + os.path.basename(self.file_path) + ".rdb"
        if os.path.exists(fn):
            return fn
        else:
            return self.file_path

    @property
    def log_file_path_if_exists(self):
        if os.path.exists(self.file_path + ".log"):
            return self.file_path + ".log"
        else:
            return None
