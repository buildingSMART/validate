import os
import sys

checks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checks"))

def execute_check(*args: str) -> list:
    return [sys.executable, *args]

def check_syntax(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.simple_spf", "--json", file_path)

def check_header_syntax(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.simple_spf", "--json", "--only-header", file_path)

def check_schema(file_path: str, task_id: int) -> list:
    return execute_check("-m", "ifcopenshell.validate", "--json", "--rules", "--fields", file_path)

def check_header(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(checks_dir, "header_policy", "validate_header.py"), file_path)

def check_digital_signatures(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(checks_dir, "signatures", "check_signatures.py"), file_path)

def check_bsdd(file_path: str, task_id: int) -> list:
    return execute_check(os.path.join(checks_dir, "check_bsdd.py"),
                        "--file-name", file_path, "--task-id", str(task_id))

def check_gherkin(file_path: str, task_id: int, rule_type: str) -> list:
    return execute_check(os.path.join(checks_dir, "check_gherkin.py"),
                        "--file-name", file_path,
                        "--task-id", str(task_id),
                        "--rule-type", rule_type)

def check_prerequisites(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "CRITICAL") + ["--purepythonparser"]

def check_normative_ia(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "IMPLEMENTER_AGREEMENT")

def check_normative_ip(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "INFORMAL_PROPOSITION")

def check_industry_practices(file_path: str, task_id: int) -> list:
    return check_gherkin(file_path, task_id, "INDUSTRY_PRACTICE")

def check_instance_completion(file_path, task_id):
    return []