from dataclasses import dataclass
import typing
import sys
import os
from apps.ifc_validation_models.models import ValidationTask, Model

def execute_check(*args: str) -> list:
    return [sys.executable, *args]

def check_syntax(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.simple_spf", "--json", file_path)

def check_header_syntax(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.simple_spf", "--json", "--only-header", file_path)

def check_schema(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.validate", "--json", "--rules", "--fields", file_path)

def check_validate_header(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(os.path.dirname(__file__), "checks", "header_policy", "validate_header.py"), file_path)

def check_signatures(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(os.path.dirname(__file__), "checks", "signatures", "check_signatures.py"), file_path)

def check_bsdd(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(os.path.dirname(__file__), "checks", "check_bsdd.py"),
                        "--file-name", file_path, "--task-id", str(task_id))

def check_gherkin(file_path: str, task_id: int, rule_type: str) -> list:
    return execute_check(os.path.join(os.path.dirname(__file__), "checks", "check_gherkin.py"),
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


@dataclass
class TaskConfig:
    type: str
    increment: int
    model_field: str
    check_program: typing.Callable[[str], list]
    blocks: typing.Optional[typing.List[str]]
    execution_stage: str = "parallel"


TASK_CONFIGS: typing.Dict[str, TaskConfig] = {
    'header_syntax_validation_subtask': TaskConfig(
        type=ValidationTask.Type.HEADER_SYNTAX,
        increment=5,
        model_field=Model.status_header_syntax,
        check_program=check_header_syntax,
        blocks=[
            'header_validation_subtask',
            'syntax_validation_subtask',
            'prerequisites_subtask',
            'digital_signatures_subtask',
            'schema_validation_subtask',
            'normative_rules_ia_validation_subtask',
            'normative_rules_ip_validation_subtask',
            'industry_practices_subtask',
            'instance_completion_subtask',
        ],
        execution_stage="serial",
    ),
    'header_validation_subtask': TaskConfig(
        type=ValidationTask.Type.HEADER,
        increment=10,
        model_field=Model.status_header,
        check_program=check_validate_header,
        blocks = [],
        execution_stage="serial",
    ),
    'syntax_validation_subtask': TaskConfig(
        type=ValidationTask.Type.SYNTAX,
        increment=5,
        model_field=Model.status_syntax,
        check_program=check_syntax,
        blocks=[
            'digital_signatures_subtask',
            'schema_validation_subtask',
            'normative_rules_ia_validation_subtask',
            'normative_rules_ip_validation_subtask',
            'industry_practices_subtask',
            'instance_completion_subtask'
        ],
        execution_stage="serial",
    ),
    'prerequisites_subtask': TaskConfig(
        type=ValidationTask.Type.PREREQUISITES,
        increment=10,
        model_field=Model.status_prereq,
        check_program=check_gherkin_prereq,
        blocks=[
            'digital_signatures_subtask',
            'schema_validation_subtask',
            'normative_rules_ia_validation_subtask',
            'normative_rules_ip_validation_subtask',
            'industry_practices_subtask',
            'instance_completion_subtask'
        ],
        execution_stage="serial",
    ),
    'schema_validation_subtask': TaskConfig(
        type=ValidationTask.Type.SCHEMA,
        increment=10,
        model_field=Model.status_schema,
        check_program=check_schema,
        blocks = [], 
        execution_stage="parallel",
    ),
    'digital_signatures_subtask': TaskConfig(
        type=ValidationTask.Type.DIGITAL_SIGNATURES,
        increment=5,
        model_field=Model.status_signatures,
        check_program=check_signatures,
        blocks = [], 
        execution_stage="parallel",
    ),
    'bsdd_validation_subtask': TaskConfig(
        type=ValidationTask.Type.BSDD,
        increment=0,
        model_field=Model.status_bsdd,
        check_program=check_bsdd,
        blocks = [], 
        execution_stage="parallel",
    ),
    'normative_rules_ia_validation_subtask': TaskConfig(
        type=ValidationTask.Type.NORMATIVE_IA,
        increment=20,
        model_field=Model.status_ia,
        check_program=check_gherkin_ia,
        blocks = [], 
        execution_stage="parallel",    ),
    'normative_rules_ip_validation_subtask': TaskConfig(
        type=ValidationTask.Type.NORMATIVE_IP,
        increment=20,
        model_field=Model.status_ip,
        check_program=check_gherkin_ip,
        blocks = [], 
        execution_stage="parallel",
    ),
    'industry_practices_subtask': TaskConfig(
        type=ValidationTask.Type.INDUSTRY_PRACTICES,
        increment=10,
        model_field=Model.status_industry_practices,
        check_program=check_gherkin_best_practice,
        blocks = [], 
        execution_stage="parallel",
    ),
    'instance_completion_subtask': TaskConfig(
        type=ValidationTask.Type.INSTANCE_COMPLETION,
        increment=5,
        model_field=None,
        check_program=lambda file_path, task_id: [],
        blocks=[],
        execution_stage="final",
    ),
}

class TaskRegistry:
    def __init__(self, config_map: dict[str, TaskConfig]):
        self._configs = config_map
        self._by_task_type = {cfg.type: name for name, cfg in config_map.items()}
        self._by_task_type_name = {cfg.type.name: name for name, cfg in config_map.items()}

    def get_config_by_celery_name(self, name: str) -> TaskConfig:
        return self._configs.get(name)

    def get_celery_name_by_task_type(self, task_type: ValidationTask.Type) -> str:
        return self._by_task_type.get(task_type)

    def get_celery_name_by_task_type_name(self, task_type_name: str) -> str:
        return self._by_task_type_name.get(task_type_name)

    def get_blocked_tasks(self, task_name: str) -> typing.List[str]:
        return self._configs[task_name].blocks or []

    def get_tasks_by_stage(self, stage: str) -> typing.List[str]:
        return [name for name, cfg in self._configs.items() if cfg.execution_stage == stage]

    def __getitem__(self, task_name: str) -> TaskConfig:
        return self._configs[task_name]
    
    def get_blockers_of(self, task_name: str) -> typing.List[str]:
        return [
            blocker_name
            for blocker_name, cfg in self._configs.items()
            if task_name in (cfg.blocks or [])
        ]

    def all(self) -> dict[str, TaskConfig]:
        return self._configs