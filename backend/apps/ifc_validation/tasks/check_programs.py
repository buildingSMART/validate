import os
import sys
import json
import subprocess
from typing import List
from dataclasses import dataclass

from apps.ifc_validation_models.settings import TASK_TIMEOUT_LIMIT
from apps.ifc_validation_models.models import Model, ValidationTask
from core.settings import ROCKSDB_FILE_SIZE_THRESHOLD_IN_MB

from .logger import logger
from .context import TaskContext

@dataclass
class proc_output:
    returncode : int
    stdout : str
    stderr : str
    args: List[str]


def run_subprocess_wait(*popen_args, check=False, **popen_kwargs):
    process = subprocess.Popen(*popen_args, **popen_kwargs)
    out_chunks, err_chunks = [], []
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                out_chunks.append(stdout or "")
                err_chunks.append(stderr or "")
                break
            except subprocess.TimeoutExpired:
                # keep looping; you can also check your own stop conditions here
                continue
    except BaseException as e:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise
    retcode = process.returncode
    stdout, stderr = "".join(out_chunks), "".join(err_chunks)
    if check and retcode != 0:
        raise subprocess.CalledProcessError(retcode, popen_args[0], output=stdout, stderr=stderr)
    return proc_output(retcode, stdout, stderr, popen_args[0] if popen_args else [])


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
    if context.rdb_file_path_if_exists == context.file_path:
        # No conversion to RocksDB has been made
        proc = run_subprocess(
            task = context.task, 
            command = [sys.executable, "-m", "ifcopenshell.validate", "--json", "--rules", "--fields", context.file_path ]
        )
    else:
        # We have a RocksDB file, which is functionally almost the same
        # except that certain errors are only present in SPF which have
        # been captured in a separate log file, which needs to be blended
        # in into the stream of other messages.
        proc = run_subprocess(
            task = context.task, 
            command=[
                sys.executable,
                "-c",
                f"""
import json
import ifcopenshell
from ifcopenshell.validate import *

logger = json_logger()

spf_filename = {json.dumps(context.file_path)}
file = ifcopenshell.open({json.dumps(context.rdb_file_path_if_exists)})
log_filename = {json.dumps(context.log_file_path_if_exists)}
if log_filename:
    log_content = open(log_filename).read()
    if log_content:
        # certain errors are only present when interacting with SPF, these
        # are captured during the conversion to RocksDB and now emitted.
        log_internal_cpp_errors(None, spf_filename, logger, log_content=log_content)

validate(file, logger, True)

def conv(x):
    if isinstance(x, ifcopenshell.entity_instance):
        return x.get_info(scalar_only=True)
    else:
        return str(x)

for x in logger.statements:
    print(json.dumps(x, default=conv))
"""])

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
            "--file-name", context.rdb_file_path_if_exists, 
            "--task-id", str(context.task.id), 
            "--rule-type", "CRITICAL", 
            "--purepythonparser"
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
            "--file-name", context.rdb_file_path_if_exists, 
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
            "--file-name", context.rdb_file_path_if_exists, 
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
            "--file-name", context.rdb_file_path_if_exists, 
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
        error_message = (
            f"Subprocess failed with exit code {proc.returncode}\n"
            f"{proc.stdout}\n{proc.stderr}"
        )
        task.mark_as_failed(error_message)
        raise RuntimeError(error_message)
    return proc.stdout

def check_rocksdb_conversion(context: TaskContext):
    if os.path.getsize(context.file_path) > ROCKSDB_FILE_SIZE_THRESHOLD_IN_MB * 1024 * 1024:
        rdb_file_path = '/tmp/' + os.path.basename(context.file_path) + '.rdb'
        log_file_path = context.file_path + '.log'
        try:
            run_subprocess(
                task = context.task, 
                command=[
                    sys.executable,
                    "-c",
                    f"""
import ifcopenshell
ifcopenshell.ifcopenshell_wrapper.set_log_format_json()
ifcopenshell.convert_path_to_rocksdb(
    {json.dumps(context.file_path)},
    {json.dumps(rdb_file_path)})
with open({json.dumps(log_file_path)}, 'w') as f:
    f.write(ifcopenshell.get_log())
"""
                ]
            )
            context.result = Model.Status.VALID if os.path.exists(rdb_file_path) else Model.Status.INVALID
        except:
            context.result = Model.Status.INVALID
    context.result = Model.Status.NOT_APPLICABLE
    return context


def run_subprocess(
    task: ValidationTask,
    command: List[str],
) -> proc_output:
    logger.debug(f'Command for {task.type}: {" ".join(command)}')
    task.set_process_details(None, command)
    try:
        proc = run_subprocess_wait(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env= os.environ.copy()
        )
        logger.info(f'test run task task name {task.type}, task value : {task}')
        return proc
    
    except Exception as err:
        logger.exception(f"{type(err).__name__} in task {task.id} : {task.type}")
        task.mark_as_failed(str(err))
        raise type(err)(f"Unknown error during validation task {task.id}: {task.type}") from err