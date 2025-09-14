import os
import sys
import json
import subprocess
from typing import List

from apps.ifc_validation_models.settings import TASK_TIMEOUT_LIMIT
from apps.ifc_validation_models.models import ValidationTask

from .logger import logger
from .context import TaskContext

checks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checks"))

def check_syntax(context:TaskContext):
    proc = run_subprocess(context.task, [sys.executable, "-m", "ifcopenshell.simple_spf", "--json", context.file_path ])
    output = proc.stdout 
    error_output = proc.stderr
    success = (len(list(filter(None, output.split("\n")))) == 0) and len(error_output) == 0
    context.result = {
        'output': proc.stdout, 
        'error_output': proc.stderr, 
        'success': success
    }
    return context

def check_header_syntax(context:TaskContext):
    proc = run_subprocess(context.task, [sys.executable, "-m", "ifcopenshell.simple_spf", "--json", "--only-header", context.file_path])
    output = proc.stdout 
    error_output = proc.stderr
    success = (len(list(filter(None, output.split("\n")))) == 0) and len(error_output) == 0
    context.result = {
        'output': proc.stdout, 
        'error_output': proc.stderr, 
        'success': success
    }
    return context

def is_schema_error(line):
    try:
        json.loads(line)
    except ValueError:
        return False 
    return True

def check_schema(context:TaskContext):
    proc = run_subprocess(
        task = context.task, 
        command = [sys.executable, "-m", "ifcopenshell.validate", "--json", "--rules", "--fields", context.file_path ]
    )
    output = list(filter(is_schema_error, proc.stdout.split("\n")))
    success = proc.returncode >= 0
    valid = len(output) == 0
    
    context.result =  {
        'output': output,
        'success': success, 
        'valid': valid
    }
    return context
    
    
def check_header(context:TaskContext):
    proc = run_subprocess(
        task=context.task,
        command=[sys.executable, os.path.join(checks_dir, "header_policy", "validate_header.py"), context.file_path] 
    )
    header_validation = {}
    for line in proc.stdout.splitlines():
        try:
            header_validation = json.loads(line)
        except json.JSONDecodeError:
            continue 
    context.result = header_validation
    return context


def check_digital_signatures(context:TaskContext):
    proc = run_subprocess(
        task=context.task,
        command=[sys.executable, os.path.join(checks_dir, "signatures", "check_signatures.py"), context.file_path] 
    )
    output = list(map(json.loads, filter(None, map(lambda s: s.strip(), proc.stdout.split("\n")))))
    success = proc.returncode >= 0
    valid = all(m['signature'] != "invalid" for m in output)
    
    context.result = {
        'output': output, 
        'success': success, 
        'valid': valid
    }
    return context
    

def check_bsdd(context:TaskContext):
    proc = run_subprocess(
        task=context.task, 
        command=[sys.executable, os.path.join(checks_dir, "check_bsdd.py"), "-file-name", context.file_path, "--task-id", str(context.task.id) ]
    )
    raw_output = check_proc_success_or_fail(proc, context.task) 
    logger.info(f'Output for {context.config.type}: {raw_output}')
    context.result = raw_output
    return context

def check_prerequisites(context:TaskContext):
    proc = run_subprocess(
        task=context.task, 
        command = [
            sys.executable, 
            os.path.join(checks_dir, "check_gherkin.py"),
            "--file-name", context.file_path, 
            "--task-id", str(context.task.id), 
            "--rule-type", "CRITICAL", 
            "--purepythonparser", 
            "--only_header" # applies to IFC101
        ]
    )
    raw_output = check_proc_success_or_fail(proc, context.task)
    context.result = raw_output
    return context

def check_normative_ia(context:TaskContext):
    proc = run_subprocess(
        task=context.task, 
        command = [
            sys.executable, 
            os.path.join(checks_dir, "check_gherkin.py"),
            "--file-name", context.file_path, 
            "--task-id", str(context.task.id), 
            "--rule-type", "IMPLEMENTER_AGREEMENT"
        ]
    )
    raw_output = check_proc_success_or_fail(proc, context.task)
    context.result = raw_output
    return context

def check_normative_ip(context:TaskContext):
    proc = run_subprocess(
        task=context.task, 
        command = [
            sys.executable, 
            os.path.join(checks_dir, "check_gherkin.py"),
            "--file-name", context.file_path, 
            "--task-id", str(context.task.id), 
            "--rule-type", "INFORMAL_PROPOSITION"
        ]
    )
    raw_output = check_proc_success_or_fail(proc, context.task)
    context.result = raw_output
    return context

def check_industry_practices(context:TaskContext):
    proc = run_subprocess(
        task=context.task, 
        command = [
            sys.executable, 
            os.path.join(checks_dir, "check_gherkin.py"),
            "--file-name", context.file_path, 
            "--task-id", str(context.task.id), 
            "--rule-type", "INDUSTRY_PRACTICE"
        ]
    )
    raw_output = check_proc_success_or_fail(proc, context.task)
    context.result = raw_output
    return context

def check_instance_completion(context:TaskContext):
    return context

def check_proc_success_or_fail(proc, task):
    if proc.returncode is not None and proc.returncode != 0:
        error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        task.mark_as_failed(error_message)
        raise RuntimeError(error_message)
    return proc.stdout

def run_subprocess(
    task: ValidationTask,
    command: List[str],
) -> subprocess.CompletedProcess[str]:
    logger.debug(f'Command for {task.type}: {" ".join(command)}')
    task.set_process_details(None, command)
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TASK_TIMEOUT_LIMIT,
            env= os.environ.copy()
        )
        logger.info(f'test run task task name {task.type}, task value : {task}')
        return proc
    
    except Exception as err:
        logger.exception(f"{type(err).__name__} in task {task.id} : {task.type}")
        task.mark_as_failed(err)
        raise type(err)(f"Unknown error during validation task {task.id}: {task.type}") from err