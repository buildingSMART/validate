import functools

from celery import shared_task, chain, chord, group

from core.utils import log_execution

from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation_models.models import *
from .configs import task_registry
from .context import TaskContext
from .utils import get_absolute_file_path
from .logger import logger
from .email_tasks import *


assert task_registry.total_increment() == 100

def check_proc_success_or_fail(proc, task):
    if proc.returncode is not None and proc.returncode != 0:
        error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        task.mark_as_failed(error_message)
        raise RuntimeError(error_message)
    return proc.stdout

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
    

def validation_task_runner(task_type):
    def decorator(func):
        @shared_task(bind=True)
        @log_execution
        @requires_django_user_context
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            id = kwargs.get('id')
            
            request = ValidationRequest.objects.get(pk=id)
            file_path = get_absolute_file_path(request.file.name)
            
            # Always create the task record, even if it will be skipped due to blocking conditions,
            # so it is logged and its status can be marked as 'skipped'
            task = ValidationTask.objects.create(request=request, type=task_type)
            
            if model := request.model:
                invalid_blockers = list(filter(
                    lambda b: getattr(model, task_registry[b].status_field.name) == Model.Status.INVALID,
                    task_registry.get_blockers_of(task_type)
                ))
            else: # for testing, we're not instantiating a model
                invalid_blockers = []
            
            # get task configuration 
            config = task_registry[task_type]
            
            # update progress
            increment = config.increment
            request.progress = min(request.progress + increment, 100)
            request.save()

            if not invalid_blockers:
                task.mark_as_initiated()
                
                # Execution Layer
                try:
                    context = config.check_program(TaskContext(
                        config=config,
                        task=task,
                        request=request,
                        file_path=file_path,
                    ))
                except Exception as err:
                    task.mark_as_failed(str(err))
                    logger.exception(f"Execution failed in task {task_type}: {task}")
                    return

                # Processing Layer / write to DB
                try:
                    reason = config.process_results(context)
                    task.mark_as_completed(reason)
                    logger.debug(f"Task {task_type} completed, reason: {reason}")
                except Exception as err:
                    task.mark_as_failed(str(err))
                    logger.exception(f"Processing failed in task {task_type}: {err}")
                    return
                
            # Handle skipped tasks              
            else:
                reason = f"Skipped due to fail in blocking tasks: {', '.join(invalid_blockers)}"
                logger.debug(reason)
                task.mark_as_skipped(reason)
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
def instance_completion_subtask(): pass

@validation_task_runner(ValidationTask.Type.NORMATIVE_IA)
def normative_rules_ia_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.NORMATIVE_IP)
def normative_rules_ip_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.PREREQUISITES)
def prerequisites_subtask(): pass

@validation_task_runner(ValidationTask.Type.SYNTAX)
def syntax_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.HEADER_SYNTAX)
def header_syntax_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.SCHEMA)
def schema_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.HEADER)
def header_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.DIGITAL_SIGNATURES)
def digital_signatures_subtask(): pass

@validation_task_runner(ValidationTask.Type.BSDD)
def bsdd_validation_subtask(): pass

@validation_task_runner(ValidationTask.Type.INDUSTRY_PRACTICES)
def industry_practices_subtask(): pass