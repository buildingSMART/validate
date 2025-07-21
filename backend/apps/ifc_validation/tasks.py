import os
import sys
import datetime
import subprocess
import functools
import json
import ifcopenshell
import typing

from celery import shared_task, chain, chord, group
from celery.utils.log import get_task_logger
from django.db import transaction
from django.db.utils import IntegrityError


from core.utils import log_execution
from core.settings import DJANGO_DB_BULK_CREATE_BATCH_SIZE

from apps.ifc_validation_models.settings import TASK_TIMEOUT_LIMIT, MEDIA_ROOT
from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation_models.models import *
from apps.ifc_validation.task_configs import TASK_CONFIGS

from .email_tasks import *

logger = get_task_logger(__name__)
    
PROGRESS_INCREMENTS = {
    'instance_completion_subtask': 5,
    'syntax_validation_subtask': 5,
    'header_syntax_validation_subtask': 5,
    'header_validation_subtask': 10,
    'prerequisites_subtask': 10,
    'schema_validation_subtask': 10,
    'digital_signatures_subtask': 5,
    'bsdd_validation_subtask': 0,
    'normative_rules_ia_validation_subtask': 20,
    'normative_rules_ip_validation_subtask': 20,
    'industry_practices_subtask': 10
}

assert sum(cfg.increment for cfg in TASK_CONFIGS.values()) == 100

class ValidationSubprocessError(Exception): pass
class ValidationTimeoutError(ValidationSubprocessError): pass
class ValidationOpenShellError(ValidationSubprocessError): pass
class ValidationIntegrityError(ValidationSubprocessError): pass

def run_task(
    task: ValidationTask,
    check_program: typing.List[str],
    task_name: str
) -> subprocess.CompletedProcess[str]:
    task.set_process_details(None, check_program)
    try:
        proc = subprocess.run(
            check_program,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=TASK_TIMEOUT_LIMIT,
            env= os.environ.copy()
        )
        return proc
    
    except subprocess.TimeoutExpired as err:
        logger.exception(f"TimeoutExpired while running task {task.id} with command: {' '.join(check_program)} : {task_name}")
        task.mark_as_failed(err)
        raise ValidationTimeoutError(f"Task {task_name} timed out") from err

    except ifcopenshell.Error as err:
        logger.exception(f"Ifcopenshell error in task {task.id} : {task_name}")
        task.mark_as_failed(err)
        raise ValidationOpenShellError(f"IFC parsing or validation failed during task {task_name}") from err

    except IntegrityError as err:
        logger.exception(f"Database integrity error in task {task.id} : {task_name}")
        task.mark_as_failed(err)
        raise ValidationIntegrityError(f"Database error during task {task_name}") from err

    except Exception as err:
        logger.exception(f"Unexpected error in task {task.id} : {task_name}")
        task.mark_as_failed(err)
        raise ValidationSubprocessError(f"Unknown error during validation task {task.id}: {task_name}") from err

def log_program(taskname, check_program):
    logger.debug(f'Command for {taskname}: {" ".join(check_program)}')

def update_progress(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return_value = func(self, *args, **kwargs)
        try:
            request_id = kwargs.get("id")
            # @nb not the most efficient because we fetch the ValidationRequest anew, but
            # assuming django will cache this efficiently enough for us to keep the code clean
            config = TASK_CONFIGS.get(func.__name__)
            request = ValidationRequest.objects.get(pk=request_id)
            increment = config.increment
            request.progress = min(request.progress + increment, 100)
            request.save()
        except Exception as e:
            print(f"Error updating progress for {func.__name__}: {e}")
        return return_value        
    return wrapper


@functools.lru_cache(maxsize=1024)
def get_absolute_file_path(file_name):

    """
    Resolves the absolute file path of an uploaded file and checks if it exists.
    It tries resolving Django MEDIA_ROOT and current working directory, and caches the result.

    Mandatory Args:
       file_name: relative file name of the uploaded file.

    Returns:
       Absolute file path of the uploaded file.
    """

    ifc_fn = os.path.join(MEDIA_ROOT, file_name)

    if not os.path.exists(ifc_fn):
        ifc_fn2 = os.path.join(os.getcwd(), ifc_fn)
        if not os.path.exists(ifc_fn2):
            raise FileNotFoundError(f"File path for file_name={file_name} was not found (tried loading '{ifc_fn}' and '{ifc_fn2}').")

    ifc_fn = os.path.abspath(ifc_fn)

    logger.debug(f"get_absolute_file_path(): file_name={file_name} returned '{ifc_fn}'")
    return ifc_fn


@shared_task(bind=True)
@log_execution
def error_handler(self, *args, **kwargs):

    on_workflow_failed.delay(*args, **kwargs)


@shared_task(bind=True)
@log_execution
def chord_error_handler(self, request, exc, traceback, *args, **kwargs):

    on_workflow_failed.apply_async([request, exc, traceback])


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def on_workflow_started(self, *args, **kwargs):

    # update status
    id = kwargs.get('id')
    reason = f"args={args} kwargs={kwargs}"
    request = ValidationRequest.objects.get(pk=id)
    request.mark_as_initiated(reason)

    # queue sending emails
    nbr_of_tasks = request.tasks.count()
    if nbr_of_tasks == 0:
        # send_acknowledgement_user_email_task.delay(id=id, file_name=request.file_name) # disabled
        send_acknowledgement_admin_email_task.delay(id=id, file_name=request.file_name)
    else:
        # send_revalidating_user_email_task.delay(id=id, file_name=request.file_name) # disabled
        send_revalidating_admin_email_task.delay(id=id, file_name=request.file_name)


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def on_workflow_completed(self, result, **kwargs):

    # update status
    id = kwargs.get('id')
    if not isinstance(id, int):
        raise ValueError(f"Invalid id: {id!r}")
    reason = "Processing completed"
    request = ValidationRequest.objects.get(pk=id)
    request.mark_as_completed(reason)

    # queue sending email
    send_completion_email_task.delay(id=id, file_name=request.file_name)


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def on_workflow_failed(self, *args, **kwargs):

    logger.debug(f'Function {self.__name__} called with args={args} kwargs={kwargs}')

    # update status
    id = args[1]
    reason = f"Processing failed: args={args} kwargs={kwargs}"
    request = ValidationRequest.objects.get(pk=id)
    request.mark_as_failed(reason)

    # queue sending email
    send_failure_email_task.delay(id=id, file_name=request.file_name)
    send_failure_admin_email_task.delay(id=id, file_name=request.file_name)


@log_execution
@requires_django_user_context
@transaction.atomic
# @requires_django_exclusive_table_lock(Model, 'EXCLUSIVE')
# --> table lock, slower - DO NOT USE
def get_or_create_ifc_model(request_id):

    id = request_id
    request = ValidationRequest.objects.get(pk=id)
    if request.model is None:

        # acquire row lock (... uses "FOR UPDATE" hint)
        request = ValidationRequest.objects.select_for_update().get(pk=id)

        model, _ = Model.objects.get_or_create(
            file_name=request.file_name,
            file=request.file,
            size=request.file.size,
            uploaded_by=request.created_by
        )
        request.model = model
        request.save()

        return model

    else:
        return request.model

def validation_task_runner(task_type):
    def decorator(func):
        @shared_task(bind=True)
        @log_execution
        @requires_django_user_context
        @update_progress
        @functools.wraps(func)
        def wrapper(self, prev_result, id, file_name, *args, **kwargs):
            if args and isinstance(args[0], dict) and "is_valid" in args[0]:
                prev_result = args[0]
            else:
                prev_result = {"is_valid": True}
                
            
            request = ValidationRequest.objects.get(pk=id)
            file_path = get_absolute_file_path(request.file.name)
            task = ValidationTask.objects.create(request=request, type=task_type)

            if prev_result is not None and prev_result.get('is_valid') is True:
                task.mark_as_initiated()
                return func(self, task, request, file_path, *args, **kwargs)
            else:
                reason = f'Skipped as prev_result = {prev_result}.'
                task.mark_as_skipped(reason)
                return {'is_valid': None, 'reason': reason}
        return wrapper
    return decorator


@shared_task(bind=True)
@log_execution
def ifc_file_validation_task(self, id, file_name, *args, **kwargs):

    if id is None or file_name is None:
        raise ValueError("Arguments 'id' and/or 'file_name' are required.")

    error_task = error_handler.s(id, file_name)
    chord_error_task = chord_error_handler.s(id, file_name)

    workflow_started = on_workflow_started.s(id=id, file_name=file_name)
    workflow_completed = on_workflow_completed.s(id=id, file_name=file_name)

    serial_tasks = chain(
        header_syntax_validation_subtask.s(id=id, file_name=file_name),
        header_validation_subtask.s(id=id, file_name=file_name),
        syntax_validation_subtask.s(id=id, file_name=file_name),
        prerequisites_subtask.s(id=id, file_name=file_name),
    )

    parallel_tasks = group([
        digital_signatures_subtask.s(id=id, file_name=file_name),
        schema_validation_subtask.s(id=id, file_name=file_name),
        #bsdd_validation_subtask.s(id=id, file_name=file_name), # disabled
        normative_rules_ia_validation_subtask.s(id=id, file_name=file_name),
        normative_rules_ip_validation_subtask.s(id=id, file_name=file_name),
        industry_practices_subtask.s(id=id, file_name=file_name)
    ])

    final_tasks = chain(
        instance_completion_subtask.s(id=id, file_name=file_name)
    )

    workflow = (
        workflow_started |
        serial_tasks |
        chord(
            chord(parallel_tasks, final_tasks).on_error(chord_error_task),
            workflow_completed
        ).on_error(chord_error_task))
    workflow.set(link_error=[error_task])
    workflow.apply_async()


@validation_task_runner(ValidationTask.Type.INSTANCE_COMPLETION)
def instance_completion_subtask(self, task, request, file_path, *args, **kwargs):
    try:
        ifc_file = ifcopenshell.open(file_path)
    except:
        reason = f'Failed to open {file_path}. Likely previous tasks also failed.'
        task.marked_as_completed(reason)
        return {'is_valid': None, 'reason': reason}
    
    if ifc_file:
        # fetch and update ModelInstance records without ifc_type
        with transaction.atomic():
            model_id = request.model.id
            model_instances = ModelInstance.objects.filter(model_id=model_id, ifc_type__in=[None, ''])
            instance_count = model_instances.count()
            logger.info(f'Retrieved {instance_count:,} ModelInstance record(s)')
            
            for inst in model_instances.iterator():
                inst.ifc_type = ifc_file[inst.stepfile_id].is_a()
                inst.save()

            # update Task info and return
            reason = f'Updated {instance_count:,} ModelInstance record(s)'
            task.mark_as_completed(reason)
            return {'is_valid': True, 'reason': reason}


@validation_task_runner(ValidationTask.Type.NORMATIVE_IA)
def normative_rules_ia_validation_subtask(self, task, request, file_path, **kwargs):
    check_program = TASK_CONFIGS['normative_rules_ia_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    return run_gherkin_subtask(self, task, request, file_path, check_program, 'status_ia')


@validation_task_runner(ValidationTask.Type.NORMATIVE_IP)
def normative_rules_ip_validation_subtask(self, task, request, file_path, **kwargs):
    check_program = TASK_CONFIGS['normative_rules_ip_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    return run_gherkin_subtask(self, task, request, file_path, check_program, 'status_ip')


@validation_task_runner(ValidationTask.Type.PREREQUISITES)
def prerequisites_subtask(self, task, request, file_path, **kwargs):
    check_program = TASK_CONFIGS['prerequisites_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    return run_gherkin_subtask(self, task, request, file_path, check_program, 'status_prereq')



@validation_task_runner(ValidationTask.Type.SYNTAX)
def syntax_validation_subtask(self, task, request, file_path, **kwargs):
    check_program = TASK_CONFIGS['syntax_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    return run_syntax_subtask(self, task, request, file_path, check_program, 'status_syntax')

@validation_task_runner(ValidationTask.Type.HEADER_SYNTAX)
def header_syntax_validation_subtask(self, task, request, file_path, **kwargs):
    check_program = TASK_CONFIGS['header_syntax_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    return run_syntax_subtask(self, task, request, file_path, check_program, 'status_header_syntax')
    

def run_syntax_subtask(self, task, request, file_path, check_program, model_status_field):
    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )
    output = proc.stdout
    error_output = proc.stderr
    success = (len(list(filter(None, output.split("\n")))) == 0) and len(error_output) == 0

    with transaction.atomic():
        model = get_or_create_ifc_model(request.id)

        if success:
            setattr(model, model_status_field, Model.Status.VALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=output if output else None
            )
        elif error_output:
            setattr(model, model_status_field, Model.Status.INVALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.ERROR,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                observed=list(filter(None, error_output.split("\n")))[-1]
            )
        else:
            messages = json.loads(output)
            setattr(model, model_status_field, Model.Status.INVALID)
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.ERROR,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                observed=messages.get("message")
            )

        model.save(update_fields=[model_status_field])

        if success:
            reason = "No IFC syntax error(s)."
            task.mark_as_completed(reason)
            return {'is_valid': True, 'reason': reason}
        else:
            reason = f"Found IFC syntax errors:\n\nConsole: \n{output}\n\nError: {error_output}"
            task.mark_as_completed(reason)
            return {'is_valid': False, 'reason': reason}
        

@validation_task_runner(ValidationTask.Type.SCHEMA)
def schema_validation_subtask(self, task, request, file_path, *args, **kwargs):
    
    check_program = TASK_CONFIGS['schema_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)

    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )
    def is_schema_error(line):
        try:
            json.loads(line) # ignoring non-JSON messages
        except ValueError:
            return False
        return True
    
    output = list(filter(is_schema_error, proc.stdout.split("\n")))

    success = proc.returncode >= 0
    valid = len(output) == 0

    with transaction.atomic():
        model = get_or_create_ifc_model(request.id)

        if valid:
            model.status_schema = Model.Status.VALID
            task.outcomes.create(
                severity=ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=None
            )
        else:
            model.status_schema = Model.Status.INVALID
            outcomes_to_save = list()
            outcomes_instances_to_save = list()

            for line in output:
                message = json.loads(line)
                outcome = ValidationOutcome(
                    severity=ValidationOutcome.OutcomeSeverity.ERROR,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR,
                    observed=message['message'],
                    feature=json.dumps({
                        'type': message['type'] if 'type' in message else None,
                        'attribute': message['attribute'] if 'attribute' in message else None
                    }),
                    validation_task=task
                )
                outcomes_to_save.append(outcome)
                if 'instance' in message and message['instance'] is not None and 'id' in message['instance'] and 'type' in message['instance']:
                    instance = ModelInstance(
                            stepfile_id=message['instance']['id'],
                            ifc_type=message['instance']['type'],
                            model=model
                        )
                    outcome.instance_id = instance.stepfile_id # store for later reference (not persisted)
                    outcomes_instances_to_save.append(instance)

            ModelInstance.objects.bulk_create(outcomes_instances_to_save, batch_size=DJANGO_DB_BULK_CREATE_BATCH_SIZE, ignore_conflicts=True) #ignore existing
            model_instances = dict(ModelInstance.objects.filter(model_id=model.id).values_list('stepfile_id', 'id')) # retrieve all

            for outcome in outcomes_to_save:
                if outcome.instance_id:
                    instance_id = model_instances[outcome.instance_id]
                    if instance_id:
                        outcome.instance_id = instance_id

            ValidationOutcome.objects.bulk_create(outcomes_to_save, batch_size=DJANGO_DB_BULK_CREATE_BATCH_SIZE)

        model.save(update_fields=['status_schema'])

        if success:
            reason = "No IFC schema errors."
            task.mark_as_completed(reason)
            return {'is_valid': True, 'reason': reason}
        else:
            reason = f"'ifcopenshell.validate' returned exit code {proc.returncode} and {len(output):,} errors."
            task.mark_as_completed(reason)
            return {'is_valid': False, 'reason': reason}


@validation_task_runner(ValidationTask.Type.HEADER)
def header_validation_subtask(self, task, request, file_path, **kwargs):
    check_program = TASK_CONFIGS['header_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    
    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )
    
    
    header_validation = {}
    stdout_lines = proc.stdout.splitlines()
    for line in stdout_lines:
        try:
            header_validation = json.loads(line)
        except json.JSONDecodeError:
            continue 

    with transaction.atomic():
        # create or retrieve Model info
        model = get_or_create_ifc_model(request.id)
        agg_status = task.determine_aggregate_status()
        model.status_prereq = agg_status
        model.size = os.path.getsize(file_path)
        logger.debug(f'Detected size = {model.size} bytes')
        
        model.schema = header_validation.get('schema_identifier')
        logger.debug(f'The schema identifier = {header_validation.get("schema")}')
        
        # time_stamp 
        if ifc_file_time_stamp := header_validation.get('time_stamp', False):
            try:
                logger.debug(f'Timestamp within file = {ifc_file_time_stamp}')
                date = datetime.datetime.strptime(ifc_file_time_stamp, "%Y-%m-%dT%H:%M:%S")
                date_with_tz = datetime.datetime(
                    date.year, 
                    date.month, 
                    date.day, 
                    date.hour, 
                    date.minute, 
                    date.second, 
                    tzinfo=datetime.timezone.utc)
                model.date = date_with_tz
            except ValueError:
                try:
                    model.date = datetime.datetime.fromisoformat(ifc_file_time_stamp)
                except ValueError:
                    pass
                
        # mvd
        model.mvd = header_validation.get('mvd')
        
        app = header_validation.get('application_name')
        
        version = header_validation.get('version')
        name = None if any(value in (None, "Not defined") for value in (app, version)) else app + ' ' + version
        company_name = header_validation.get('company_name')
        logger.debug(f'Detected Authoring Tool in file = {name}')
        
        validation_errors = header_validation.get('validation_errors', [])
        invalid_marker_fields = ['originating_system', 'version', 'company_name', 'application_name']
        if any(field in validation_errors for field in invalid_marker_fields):
            model.status_header = Model.Status.INVALID
        else:
            # parsing was successful and model can be considered for scorecards
            model.status_header = Model.Status.VALID
            authoring_tool = AuthoringTool.find_by_full_name(full_name=name)
            if (isinstance(authoring_tool, AuthoringTool)):
                
                if authoring_tool.company is None:
                    company, _ = Company.objects.get_or_create(name=company_name)
                    authoring_tool.company = company
                    authoring_tool.save()
                    logger.debug(f'Updated existing Authoring Tool with company: {company.name}')

                model.produced_by = authoring_tool
                logger.debug(f'Retrieved existing Authoring Tool from DB = {model.produced_by.full_name}')

            elif authoring_tool is None:
                company, _ = Company.objects.get_or_create(name=company_name)
                authoring_tool, _ = AuthoringTool.objects.get_or_create(
                    company=company,
                    name=app,
                    version=version
                )
                model.produced_by = authoring_tool
                logger.debug(f'Authoring app not found, ApplicationFullName = {app}, Version = {version} - created new instance')
            else:
                model.produced_by = None
                logger.warning(f'Retrieved multiple Authoring Tool from DB: {authoring_tool} - could not assign any')  
                        
        # update header validation
        model.header_validation = header_validation
        model.save(update_fields=['status_header', 'header_validation'])
        model.save()
        
        
        # update Task info and return
        is_valid = agg_status != Model.Status.INVALID
        reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {header_validation}'
        task.mark_as_completed(reason)
        return {'is_valid': is_valid, 'reason': reason}

    

@validation_task_runner(ValidationTask.Type.DIGITAL_SIGNATURES)
def digital_signatures_subtask(self, task, request, file_path, **kwargs):
    check_script = os.path.join(os.path.dirname(__file__), "checks", "signatures", "check_signatures.py")
    
    check_program = [sys.executable, check_script, file_path]
    log_program(self.__qualname__, check_program)
    
    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )
    
    output = list(map(json.loads, filter(None, map(lambda s: s.strip(), proc.stdout.split("\n")))))
    success = proc.returncode >= 0
    valid = all(m['signature'] != "invalid" for m in output)
    
    with transaction.atomic():

        # create or retrieve Model info
        model = get_or_create_ifc_model(request.id)
        model.status_signatures = Model.Status.NOT_APPLICABLE if not output else Model.Status.VALID if valid else Model.Status.INVALID 

        def create_outcome(di):
            return ValidationOutcome(
                severity=ValidationOutcome.OutcomeSeverity.ERROR if di.get("signature") == "invalid" else ValidationOutcome.OutcomeSeverity.PASSED,
                outcome_code=ValidationOutcome.ValidationOutcomeCode.VALUE_ERROR if di.get("signature") == "invalid" else ValidationOutcome.ValidationOutcomeCode.PASSED,
                observed=di,
                feature=json.dumps({'digital_signature': 1}),
                validation_task = task
            )

        ValidationOutcome.objects.bulk_create(list(map(create_outcome, output)), batch_size=DJANGO_DB_BULK_CREATE_BATCH_SIZE)

        model.save(update_fields=['status_signatures'])

        if success:
            reason = 'Digital signature check completed'
            task.mark_as_completed(reason)
            return {'is_valid': True, 'reason': reason}
        else:
            reason = f"Script returned exit code {proc.returncode} and {proc.stderr}"
            task.mark_as_completed(reason)
            return {'is_valid': False, 'reason': reason}


@validation_task_runner(ValidationTask.Type.BSDD)
def bsdd_validation_subtask(self, task, request, file_path, *args, **kwargs):
    check_program = TASK_CONFIGS['bsdd_validation_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)
    
    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )
    
    if proc.returncode is not None and proc.returncode != 0:
        error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        task.mark_as_failed(error_message)
        raise RuntimeError(error_message)
    
    raw_output = proc.stdout 
    logger.info(f'Output for {self.__name__}: {raw_output}')

    with transaction.atomic():

        # create or retrieve Model info
        model = get_or_create_ifc_model(request.id)

        # update Validation Outcomes
        json_output = json.loads(raw_output)
        for message in json_output['messages']:

            outcome = task.outcomes.create(
                severity=[c[0] for c in ValidationOutcome.OutcomeSeverity.choices if c[1] == (message['severity'])][0],
                outcome_code=[c[0] for c in ValidationOutcome.ValidationOutcomeCode.choices if c[1] == (message['outcome'])][0],
                observed=message['message'],
                feature=json.dumps({
                    'rule': message['rule'] if 'rule' in message else None,
                    'category': message['category'] if 'category' in message else None,
                    'dictionary': message['dictionary'] if 'dictionary' in message else None,
                    'class': message['class'] if 'class' in message else None,
                    'instance_id': message['instance_id'] if 'instance_id' in message else None
                })                    
            )

            if 'instance_id' in message and message['instance_id'] is not None:
                instance, _ = model.instances.get_or_create(
                    stepfile_id = message['instance_id'],
                    model=model
                )
                outcome.instance = instance
                outcome.save()
        
        # update Model info
        agg_status = task.determine_aggregate_status()
        model.status_bsdd = agg_status
        model.save(update_fields=['status_bsdd'])

        # update Task info and return
        is_valid = agg_status != Model.Status.INVALID
        reason = f"agg_status = {Model.Status(agg_status).label}\nmessages = {json_output['messages']}"
        task.mark_as_completed(reason)
        return {'is_valid': is_valid, 'reason': reason}


@validation_task_runner(ValidationTask.Type.INDUSTRY_PRACTICES)
def industry_practices_subtask(self, task, request, file_path):
    check_program = TASK_CONFIGS['industry_practices_subtask'].check_program(file_path, task.id)
    log_program(self.__qualname__, check_program)

    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )

    if proc.returncode is not None and proc.returncode != 0:
        error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        task.mark_as_failed(error_message)
        raise RuntimeError(error_message)

    raw_output = proc.stdout

    with transaction.atomic():
        model = get_or_create_ifc_model(request.id)
        agg_status = task.determine_aggregate_status()
        model.status_industry_practices = agg_status
        model.save(update_fields=['status_industry_practices'])

        is_valid = agg_status != Model.Status.INVALID
        reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {raw_output}'
        task.mark_as_completed(reason)
        return {'is_valid': is_valid, 'reason': reason}


def run_gherkin_subtask(self, task, request, file_path, check_program, status_field):
    log_program(self.__qualname__, check_program)

    proc = run_task(
        task=task,
        check_program = check_program,
        task_name = self.name.split(".")[-1]
    )

    if proc.returncode is not None and proc.returncode != 0:
        error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        task.mark_as_failed(error_message)
        raise RuntimeError(error_message)

    raw_output = proc.stdout

    with transaction.atomic():
        model = get_or_create_ifc_model(request.id)
        agg_status = task.determine_aggregate_status()
        setattr(model, status_field, agg_status)
        model.save(update_fields=[status_field])

        is_valid = agg_status != Model.Status.INVALID
        reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {raw_output}'
        task.mark_as_completed(reason)
        return {'is_valid': is_valid, 'reason': reason}
