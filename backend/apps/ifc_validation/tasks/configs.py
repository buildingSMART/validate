from dataclasses import dataclass
from typing import List, Optional, Callable
from apps.ifc_validation_models.models import ValidationTask, Model
from . import check_programs # execution layer
from . import processing # processing layer

@dataclass
class TaskConfig:
    type: str
    increment: int
    status_field: Optional[str]
    check_program: Callable[[str, int], list]
    blocks: Optional[List[str]]
    execution_stage: str = "parallel"
    process_results: Callable | None = None

# create blueprint
def make_task(*, type, increment, field=None, stage="parallel"):
    def _load_function(module, prefix, type):
        func_name = f"{prefix}_{type.name.lower()}"
        try:
            return getattr(module, func_name)
        except AttributeError:
            raise ImportError(
                f"Missing `{prefix}` function for task type '{type.name}'. "
                f"Expected `{func_name}()` in `{module.__name__}.py`."
            ) from None

    check_program = _load_function(check_programs, "check", type)
    process_results = _load_function(processing, "process", type)
        
    return TaskConfig(
        type=type,
        increment=increment,
        status_field=Model._meta.get_field(field) if field else None,
        check_program=check_program,
        blocks=[],
        execution_stage=stage,
        process_results = process_results
    )

# define task info
header_syntax       = make_task(type=ValidationTask.Type.HEADER_SYNTAX, increment=5, field='status_header_syntax', stage="serial")
header              = make_task(type=ValidationTask.Type.HEADER,        increment=10, field='status_header',      stage="serial")
syntax              = make_task(type=ValidationTask.Type.SYNTAX,        increment=5,  field='status_syntax',      stage="serial")
prerequisites       = make_task(type=ValidationTask.Type.PREREQUISITES, increment=10, field='status_prereq',      stage="serial")
schema              = make_task(type=ValidationTask.Type.SCHEMA,        increment=10, field='status_schema')
digital_signatures  = make_task(type=ValidationTask.Type.DIGITAL_SIGNATURES, increment=5,  field='status_signatures')
bsdd                = make_task(type=ValidationTask.Type.BSDD,          increment=0,  field='status_bsdd')
normative_ia        = make_task(type=ValidationTask.Type.NORMATIVE_IA,  increment=20, field='status_ia')
normative_ip        = make_task(type=ValidationTask.Type.NORMATIVE_IP,  increment=20, field='status_ip')
industry_practices  = make_task(type=ValidationTask.Type.INDUSTRY_PRACTICES, increment=10, field='status_industry_practices')
instance_completion = make_task(type=ValidationTask.Type.INSTANCE_COMPLETION, increment=5, field=None,           stage="final")

# block tasks on error
post_tasks = [digital_signatures, schema, normative_ia, normative_ip, industry_practices, instance_completion]
header_syntax.blocks = [header, syntax, prerequisites] + post_tasks
syntax.blocks = post_tasks.copy()
prerequisites.blocks = post_tasks.copy()

# register
ALL_TASKS = [
    header_syntax, header, syntax, prerequisites,
    schema, digital_signatures, bsdd,
    normative_ia, normative_ip, industry_practices, instance_completion,
]
class TaskRegistry:
    def __init__(self, config_map: dict[str, TaskConfig]):
        self._configs = config_map
        self._by_task_type = {cfg.type: name for name, cfg in config_map.items()}
        self._by_task_type_name = {cfg.type.name: name for name, cfg in config_map.items()}

    def get_config_by_celery_name(self, name: str) -> TaskConfig:
        return self._configs[self.get_task_type_from_celery_name(name)]

    def get_celery_name_by_task_type(self, task_type: ValidationTask.Type) -> str:
        return self._by_task_type.get(task_type)

    def get_celery_name_by_task_type_name(self, task_type_name: str) -> str:
        return self._by_task_type_name.get(task_type_name)

    def get_blocked_tasks(self, task_type: ValidationTask.Type) -> List[TaskConfig]:
        return self._configs[task_type].blocks or []

    def get_tasks_by_stage(self, stage: str) -> List[str]:
        return [cfg for cfg in self._configs.values() if cfg.execution_stage == stage]

    def __getitem__(self, task_type: ValidationTask.Type) -> TaskConfig:
        return self._configs[task_type]
    
    def get_blockers_of(self, task_type: ValidationTask.Type) -> List[ValidationTask.Type]:
        return [
            blocker_type
            for blocker_type, cfg in self._configs.items()
            if any(block.type == task_type for block in cfg.blocks or [])
        ]
        
    def all(self) -> dict[str, TaskConfig]:
        return self._configs
    
    def total_increment(self) -> int:
        return sum(cfg.increment for cfg in self._configs.values())
    
task_registry = TaskRegistry({task.type: task for task in ALL_TASKS})