from dataclasses import dataclass
import typing
import sys
import os
from apps.ifc_validation_models.models import ValidationTask

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

TASK_CONFIGS: typing.Dict[str, TaskConfig] = {
    'instance_completion_subtask': TaskConfig(
        type=ValidationTask.Type.INSTANCE_COMPLETION,
        increment=5,
        model_field=None,
        check_program=lambda file_path, task_id: []  # No external check
    ),
    'syntax_validation_subtask': TaskConfig(
        type=ValidationTask.Type.SYNTAX,
        increment=5,
        model_field='status_syntax',
        check_program=check_syntax
    ),
    'header_syntax_validation_subtask': TaskConfig(
        type=ValidationTask.Type.HEADER_SYNTAX,
        increment=5,
        model_field='status_header_syntax',
        check_program=check_header_syntax
    ),
    'header_validation_subtask': TaskConfig(
        type=ValidationTask.Type.HEADER,
        increment=10,
        model_field='status_header',
        check_program=check_validate_header
    ),
    'prerequisites_subtask': TaskConfig(
        type=ValidationTask.Type.PREREQUISITES,
        increment=10,
        model_field='status_prereq',
        check_program=check_gherkin_prereq
    ),
    'schema_validation_subtask': TaskConfig(
        type=ValidationTask.Type.SCHEMA,
        increment=10,
        model_field='status_schema',
        check_program=check_schema
    ),
    'digital_signatures_subtask': TaskConfig(
        type=ValidationTask.Type.DIGITAL_SIGNATURES,
        increment=5,
        model_field='status_signatures',
        check_program=check_signatures
    ),
    'bsdd_validation_subtask': TaskConfig(
        type=ValidationTask.Type.BSDD,
        increment=0,
        model_field='status_bsdd',
        check_program=check_bsdd
    ),
    'normative_rules_ia_validation_subtask': TaskConfig(
        type=ValidationTask.Type.NORMATIVE_IA,
        increment=20,
        model_field='status_ia',
        check_program=check_gherkin_ia
    ),
    'normative_rules_ip_validation_subtask': TaskConfig(
        type=ValidationTask.Type.NORMATIVE_IP,
        increment=20,
        model_field='status_ip',
        check_program=check_gherkin_ip
    ),
    'industry_practices_subtask': TaskConfig(
        type=ValidationTask.Type.INDUSTRY_PRACTICES,
        increment=10,
        model_field='status_industry_practices',
        check_program=check_gherkin_best_practice
    ),
}