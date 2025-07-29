from dataclasses import dataclass
from typing import List, Optional, Callable
import sys
import os
from apps.ifc_validation_models.models import ValidationTask, Model

checks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checks"))

def execute_check(*args: str) -> list:
    return [sys.executable, *args]

def check_syntax(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.simple_spf", "--json", file_path)

def check_header_syntax(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.simple_spf", "--json", "--only-header", file_path)

def check_schema(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.validate", "--json", "--rules", "--fields", file_path)

def check_validate_header(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(checks_dir, "header_policy", "validate_header.py"), file_path)

def check_signatures(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(checks_dir, "signatures", "check_signatures.py"), file_path)

def check_bsdd(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(checks_dir, "check_bsdd.py"),
                        "--file-name", file_path, "--task-id", str(task_id))

def check_gherkin(file_path: str, task_id: int, rule_type: str) -> list:
    return execute_check(os.path.join(checks_dir, "check_gherkin.py"),
                        "--file-name", file_path,
                        "--task-id", str(task_id),
                        "--rule-type", rule_type)

def check_gherkin_prereq(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "CRITICAL") + ["--purepythonparser"]

def check_gherkin_ia(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "IMPLEMENTER_AGREEMENT")

def check_gherkin_ip(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "INFORMAL_PROPOSITION")

def check_gherkin_best_practice(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "INDUSTRY_PRACTICE")

def check_instance_completion(file_path, task_id):
    return []

@dataclass
class TaskConfig:
    type: str
    increment: int
    status_field: Optional[str]
    check_program: Callable[[str], list]
    blocks: Optional[List[str]]
    execution_stage: str = "parallel"
    run: Callable | None = None


# create blueprint
def make_task(*, type, increment, field=None, check, stage="parallel"):
    return TaskConfig(
        type=type,
        increment=increment,
        status_field=Model._meta.get_field(field) if field else None,
        check_program=check,
        blocks=[],
        execution_stage=stage,
    )

# define task info for celery
header_syntax       = make_task(type=ValidationTask.Type.HEADER_SYNTAX, increment=5, field='status_header_syntax', check=check_header_syntax, stage="serial")
header              = make_task(type=ValidationTask.Type.HEADER,        increment=10, field='status_header',        check=check_validate_header, stage="serial")
syntax              = make_task(type=ValidationTask.Type.SYNTAX,        increment=5,  field='status_syntax',        check=check_syntax, stage="serial")
prereq              = make_task(type=ValidationTask.Type.PREREQUISITES, increment=10, field='status_prereq',        check=check_gherkin_prereq, stage="serial")
schema              = make_task(type=ValidationTask.Type.SCHEMA,        increment=10, field='status_schema',        check=check_schema)
digital_signatures  = make_task(type=ValidationTask.Type.DIGITAL_SIGNATURES, increment=5,  field='status_signatures', check=check_signatures)
bsdd                = make_task(type=ValidationTask.Type.BSDD,          increment=0,  field='status_bsdd',          check=check_bsdd)
normative_ia        = make_task(type=ValidationTask.Type.NORMATIVE_IA,  increment=20, field='status_ia',            check=check_gherkin_ia)
normative_ip        = make_task(type=ValidationTask.Type.NORMATIVE_IP,  increment=20, field='status_ip',            check=check_gherkin_ip)
industry_practices  = make_task(type=ValidationTask.Type.INDUSTRY_PRACTICES, increment=10, field='status_industry_practices', check=check_gherkin_best_practice)
instance_completion = make_task(type=ValidationTask.Type.INSTANCE_COMPLETION, increment=5, field=None,                    check=check_instance_completion, stage="final")

# block tasks on error
post_tasks = [digital_signatures, schema, normative_ia, normative_ip, industry_practices, instance_completion]
header_syntax.blocks = [header, syntax, prereq] + post_tasks
syntax.blocks = post_tasks.copy()
prereq.blocks = post_tasks.copy()

# register
ALL_TASKS = [
    header_syntax, header, syntax, prereq,
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
