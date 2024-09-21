import os
import sys
import datetime
import subprocess
import functools
import json
import ifcopenshell

from celery import shared_task, chain, chord, group
from celery.utils.log import get_task_logger
from django.db import transaction

from core.utils import log_execution

from apps.ifc_validation_models.settings import TASK_TIMEOUT_LIMIT, MEDIA_ROOT
from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation_models.models import *

from .email_tasks import *

logger = get_task_logger(__name__)


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
    id = self.request.args[0]
    reason = f"args={args} kwargs={kwargs}"
    request = ValidationRequest.objects.get(pk=id)
    request.mark_as_initiated(reason)

    # queue sending emails
    nbr_of_tasks = request.tasks.count()
    if nbr_of_tasks == 0:
        send_acknowledgement_user_email_task.delay(id=id, file_name=request.file_name)
        send_acknowledgement_admin_email_task.delay(id=id, file_name=request.file_name)
    else:
        send_revalidating_user_email_task.delay(id=id, file_name=request.file_name)
        send_revalidating_admin_email_task.delay(id=id, file_name=request.file_name)


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def on_workflow_completed(self, *args, **kwargs):

    # update status
    id = args[1]
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


@shared_task(bind=True)
@log_execution
def ifc_file_validation_task(self, id, file_name, *args, **kwargs):

    if id is None or file_name is None:
        raise ValueError("Arguments 'id' and/or 'file_name' are required.")

    error_task = error_handler.s(id, file_name)
    chord_error_task = chord_error_handler.s(id, file_name)

    workflow_started = on_workflow_started.s(id, file_name)
    workflow_completed = on_workflow_completed.s(id, file_name)

    serial_tasks = chain(
        syntax_validation_subtask.s(id, file_name),
        parse_info_subtask.s(id, file_name),
        prerequisites_subtask.s(id, file_name)
    )

    parallel_tasks = group([
        schema_validation_subtask.s(id, file_name),
        #bsdd_validation_subtask.s(id, file_name), # disabled
        normative_rules_ia_validation_subtask.s(id, file_name),
        normative_rules_ip_validation_subtask.s(id, file_name),
        industry_practices_subtask.s(id, file_name)
    ])

    final_tasks = chain(
        instance_completion_subtask.s(id, file_name)
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


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def instance_completion_subtask(self, prev_result, id, file_name, *args, **kwargs):

    prev_result_succeeded = prev_result is not None and prev_result[0]['is_valid'] is True
    if prev_result_succeeded:

        request = ValidationRequest.objects.get(pk=id)
        file_path = get_absolute_file_path(request.file.name)

        try:
            ifc_file = ifcopenshell.open(file_path)
        except:
            logger.warning(f'Failed to open {file_path}. Likely previous tasks also failed.')
            ifc_file = None

        if ifc_file:
            with transaction.atomic():
                for inst in request.model.instances.iterator():
                    inst.ifc_type = ifc_file[inst.stepfile_id].is_a()
                    inst.save()

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        #task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def syntax_validation_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # set overall progress
    PROGRESS_INCREMENT = 10
    request.progress = PROGRESS_INCREMENT
    request.save()

    # determine program/script to run
    check_script = os.path.join(os.path.dirname(__file__), "checks", "step_file_parser", "main.py")
    check_program = [sys.executable, check_script, '--json', file_path]
    logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.SYNTAX)
    task.mark_as_initiated()

    # check syntax
    try:

        # note: use run instead of Popen b/c PIPE output can be very big...
        task.set_process_details(None, check_program)  # run() has no pid...
        proc = subprocess.run(
            check_program,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=TASK_TIMEOUT_LIMIT
        )

        # parse output
        output = proc.stdout
        error_output = proc.stderr
        success = (len(list(filter(None, output.split("\n")))) == 0) and len(proc.stderr) == 0

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

            # update Model info
            if success:
                model.status_syntax = Model.Status.VALID
                task.outcomes.create(
                    severity=ValidationOutcome.OutcomeSeverity.PASSED,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                    observed=output if output != '' else None
                )

            elif len(error_output) != 0:
                model.status_syntax = Model.Status.INVALID
                task.outcomes.create(
                    severity=ValidationOutcome.OutcomeSeverity.ERROR,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                    observed=list(filter(None, proc.stderr.split("\n")))[-1] # last line of traceback
                )

            else:
                messages = json.loads(output)
                model.status_syntax = Model.Status.INVALID
                task.outcomes.create(
                    severity=ValidationOutcome.OutcomeSeverity.ERROR,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.SYNTAX_ERROR,
                    observed=messages['message'] if 'message' in messages else None
                )

            model.save(update_fields=['status_syntax'])

            # store and return
            if success:
                reason = "No IFC syntax error(s)."
                task.mark_as_completed(reason)
                return {'is_valid': True, 'reason': task.status_reason}
            else:
                reason = f"Found IFC syntax errors:\n\nConsole: \n{output}\n\nError: {error_output}"
                task.mark_as_completed(reason)
                return {'is_valid': False, 'reason': reason}

    except subprocess.TimeoutExpired as err:
        task.mark_as_failed(err)
        raise

    except Exception as err:
        task.mark_as_failed(err)
        raise


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def parse_info_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 10
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.PARSE_INFO)

    prev_result_succeeded = prev_result is not None and prev_result['is_valid'] is True
    if prev_result_succeeded:

        task.mark_as_initiated()

        # retrieve IFC info
        try:
            task.set_process_details(None, f"(module) ifcopenshell.open() for file '{file_path}')")

            with transaction.atomic():

                ifc_file = ifcopenshell.open(file_path)
                logger.info(f'Opened file {file_path} in ifcopenshell; schema = {ifc_file.schema}')

                # create or retrieve Model info
                model = get_or_create_ifc_model(id)

                # size
                model.size = os.path.getsize(file_path)
                logger.debug(f'Detected size = {model.size} bytes')

                # schema
                model.schema = ifc_file.schema_identifier
                logger.debug(f'Detected schema = {model.schema}')

                # date - format eg. 2024-02-25T10:05:22 - tz defaults to UTC
                model.date = None
                try:
                    ifc_file_time_stamp = f'{ifc_file.header.file_name.time_stamp}'
                except RuntimeError:
                    ifc_file_time_stamp = None
                    model.date = None
                if ifc_file_time_stamp:
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
                        model.date = datetime.datetime.fromisoformat(ifc_file_time_stamp)
                logger.debug(f'Detected date = {model.date}')

                # MVD
                try:
                    model.mvd = ifc_file.header.file_description.description[0].split(" ", 1)[1][1:-1]
                except:
                    model.mvd = None
                logger.debug(f'Detected MVD = {model.mvd}')

                # authoring app
                try:
                    app = ifc_file.by_type("IfcApplication")[0].ApplicationFullName if len(ifc_file.by_type("IfcApplication")) > 0 else None
                except RuntimeError:
                    app = None
                try:
                    version = ifc_file.by_type("IfcApplication")[0].Version if len(ifc_file.by_type("IfcApplication")) > 0 else None
                except RuntimeError:
                    version = None
                name = None if (app is None and version is None) else (None if version is None else app + ' ' + version)
                logger.debug(f'Detected Authoring Tool in file = {name}')

                if name is not None:
                    authoring_tool = AuthoringTool.find_by_full_name(full_name=name)
                    if (isinstance(authoring_tool, AuthoringTool)):

                        model.produced_by = authoring_tool
                        logger.debug(f'Retrieved existing Authoring Tool from DB = {model.produced_by.full_name}')

                    elif authoring_tool is None:
                        authoring_tool, _ = AuthoringTool.objects.get_or_create(
                            name=app,
                            version=version
                        )
                        model.produced_by = authoring_tool
                        logger.debug(f'Authoring app not found, ApplicationFullName = {app}, Version = {version} - created new instance')
                    else:
                        model.produced_by = None
                        logger.warning(f'Retrieved multiple Authoring Tool from DB: {authoring_tool} - could not assign any')

                # number of elements/geometries/properties
                try:
                    model.number_of_elements = len(ifc_file.by_type("IfcBuildingElement"))
                except:
                    model.number_of_elements = len(ifc_file.by_type("IfcBuiltElement"))
                model.number_of_geometries = len(ifc_file.by_type("IfcShapeRepresentation"))
                model.number_of_properties = len(ifc_file.by_type("IfcProperty"))
                logger.debug(f'Found {model.number_of_elements} elements, {model.number_of_geometries} geometries and {model.number_of_properties} properties')

                # save all changes
                model.save()

                reason = f'IFC info parsed and stored in Model #{model.id}.'
                task.mark_as_completed(reason)
                return {'is_valid': True, 'reason': reason}

        except ifcopenshell.Error as err:
            reason = str(err)
            task.mark_as_completed(reason)
            return {'is_valid': False, 'reason': reason}

        except Exception as err:
            task.mark_as_failed(err)
            raise

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def prerequisites_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 15
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.PREREQUISITES)

    prev_result_succeeded = prev_result is not None and prev_result['is_valid'] is True
    if prev_result_succeeded:

        task.mark_as_initiated()

        # determine program/script to run
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_gherkin.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task.id), '--rule-type', 'CRITICAL']
        logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

        # check Gherkin IP
        try:
            # note: use run instead of Popen b/c PIPE output can be very big...
            proc = subprocess.run(
                check_program,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=TASK_TIMEOUT_LIMIT,
                env=os.environ.copy()
            )
            task.set_process_details(None, check_program)  # run() has no pid...

        except subprocess.TimeoutExpired as err:
            task.mark_as_failed(err)
            raise

        except Exception as err:
            task.mark_as_failed(err)
            raise

        if (proc.returncode is not None and proc.returncode != 0) or (len(proc.stderr) > 0):
            error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
            task.mark_as_failed(error_message)
            raise RuntimeError(error_message)

        raw_output = proc.stdout

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

            # update Model info
            agg_status = task.determine_aggregate_status()
            model.status_prereq = agg_status
            model.save(update_fields=['status_prereq'])

            # update Task info and return
            is_valid = agg_status != Model.Status.INVALID
            reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {raw_output}'
            task.mark_as_completed(reason)
            return {'is_valid': is_valid, 'reason': reason}

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def schema_validation_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 10
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.SCHEMA)

    # TODO: revisit schema validation task, perhaps change order of flow?
    prev_result_succeeded = prev_result is not None and (prev_result['is_valid'] is True or 'Unsupported schema' in prev_result['reason'])
    if prev_result_succeeded:

        task.mark_as_initiated()

        # determine program/script to run
        check_program = [sys.executable, '-m', 'ifcopenshell.validate', '--json', '--rules', '--fields', file_path]
        logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

        # check schema
        try:
            # note: use run instead of Popen b/c PIPE output can be very big...
            proc = subprocess.run(
                check_program,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=TASK_TIMEOUT_LIMIT
            )
            task.set_process_details(None, check_program)  # run() has no pid...
        except subprocess.TimeoutExpired as err:
            task.mark_as_failed(err)
            raise
        except ifcopenshell.Error as err:
            # logical validation error OR C++ errors
            task.mark_as_failed(err)
            pass
        except Exception as err:
            task.mark_as_failed(err)
            raise

        # schema check returns either multiple JSON lines, or a single line message, or nothing.        
        def is_schema_error(line):
            try:
                json.loads(line) # ignoring non-JSON messages
            except ValueError:
                return False
            return True
        
        output = list(filter(is_schema_error, proc.stdout.split("\n")))
        # success = (len(output) == 0)
        # tfk: if we mark this task as failed we don't do the instance population either.
        # marking as failed should probably be reserved for blocking errors (prerequisites)
        # and internal errors and differentiate between valid and task_success.
        success = proc.returncode == 0
        valid = (len(output) == 0)

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

            # update Model and Validation Outcomes
            if valid:
                model.status_schema = Model.Status.VALID
                task.outcomes.create(
                    severity=ValidationOutcome.OutcomeSeverity.PASSED,
                    outcome_code=ValidationOutcome.ValidationOutcomeCode.PASSED,
                    observed=None
                )
            else:
                for line in output:
                    message = json.loads(line)
                    model.status_schema = Model.Status.INVALID
                    outcome = task.outcomes.create(
                        severity=ValidationOutcome.OutcomeSeverity.ERROR,
                        outcome_code=ValidationOutcome.ValidationOutcomeCode.SCHEMA_ERROR,
                        observed=message['message'],
                        feature=json.dumps({
                            'type': message['type'] if 'type' in message else None,
                            'attribute': message['attribute'] if 'attribute' in message else None
                        }),
                    )

                    if 'instance' in message and message['instance'] is not None and 'id' in message['instance'] and 'type' in message['instance']:
                        instance, _ = model.instances.get_or_create(
                            stepfile_id=message['instance']['id'],
                            ifc_type=message['instance']['type'],
                            model=model
                        )
                        outcome.instance = instance
                        outcome.save()

            model.save(update_fields=['status_schema'])

            # return
            if success:
                reason = 'No IFC schema errors.'
                task.mark_as_completed(reason)
                return {'is_valid': True, 'reason': reason}
            else:
                reason = f"'ifcopenshell.validate' returned exit code {proc.returncode} and {len(output):,} errors : {output}"
                task.mark_as_completed(reason)
                return {'is_valid': False, 'reason': reason}

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def bsdd_validation_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 10
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.BSDD)

    prev_result_succeeded = prev_result is not None and prev_result['is_valid'] is True
    if prev_result_succeeded:

        task.mark_as_initiated()

        # determine program/script to run
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_bsdd.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(id)]
        logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

        # check bSDD
        try:
            # note: use run instead of Popen b/c PIPE output can be very big...
            proc = subprocess.run(
                check_program,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=TASK_TIMEOUT_LIMIT,
                env=os.environ.copy()
            )
            task.set_process_details(None, check_program)  # run() has no pid...

        except subprocess.TimeoutExpired as err:
            task.mark_as_failed(err)
            raise

        except Exception as err:
            task.mark_as_failed(err)
            raise

        if (proc.returncode is not None and proc.returncode != 0) or (len(proc.stderr) > 0):
            error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
            task.mark_as_failed(error_message)
            raise RuntimeError(error_message)

        raw_output = proc.stdout

        logger.info(f'Output for {self.__name__}: {raw_output}')

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

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

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def normative_rules_ia_validation_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 15
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.NORMATIVE_IA)

    prev_result_succeeded = prev_result is not None and prev_result['is_valid'] is True
    if prev_result_succeeded:

        task.mark_as_initiated()

        # determine program/script to run
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_gherkin.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task.id), '--rule-type', 'IMPLEMENTER_AGREEMENT']
        logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

        # check Gherkin IA
        try:
            # note: use run instead of Popen b/c PIPE output can be very big...
            proc = subprocess.run(
                check_program,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=TASK_TIMEOUT_LIMIT,
                env=os.environ.copy()
            )
            task.set_process_details(None, check_program)  # run() has no pid...

        except subprocess.TimeoutExpired as err:
            task.mark_as_failed(err)
            raise

        except Exception as err:
            task.mark_as_failed(err)
            raise

        if (proc.returncode is not None and proc.returncode != 0) or (len(proc.stderr) > 0):
            error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
            task.mark_as_failed(error_message)
            raise RuntimeError(error_message)

        raw_output = proc.stdout

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

            # update Model info
            agg_status = task.determine_aggregate_status()
            logger.debug(f'Aggregate status for {self.__qualname__}: {agg_status}')
            model.status_ia = agg_status
            model.save(update_fields=['status_ia'])

            # update Task info and return
            is_valid = agg_status != Model.Status.INVALID
            reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {raw_output}'
            task.mark_as_completed(reason)
            return {'is_valid': is_valid, 'reason': reason}

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def normative_rules_ip_validation_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 15
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.NORMATIVE_IP)

    prev_result_succeeded = prev_result is not None and prev_result['is_valid'] is True
    if prev_result_succeeded:

        task.mark_as_initiated()

        # determine program/script to run
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_gherkin.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task.id), '--rule-type', 'INFORMAL_PROPOSITION']
        logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

        # check Gherkin IP
        try:
            # note: use run instead of Popen b/c PIPE output can be very big...
            proc = subprocess.run(
                check_program,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=TASK_TIMEOUT_LIMIT
            )
            task.set_process_details(None, check_program)  # run() has no pid...

        except subprocess.TimeoutExpired as err:
            task.mark_as_failed(err)
            raise

        except Exception as err:
            task.mark_as_failed(err)
            raise

        if (proc.returncode is not None and proc.returncode != 0) or (len(proc.stderr) > 0):
            error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
            task.mark_as_failed(error_message)
            raise RuntimeError(error_message)

        raw_output = proc.stdout

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

            # update Model info
            agg_status = task.determine_aggregate_status()
            model.status_ip = agg_status
            model.save(update_fields=['status_ip'])

            # update Task info and return
            is_valid = agg_status != Model.Status.INVALID
            reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {raw_output}'
            task.mark_as_completed(reason)
            return {'is_valid': is_valid, 'reason': reason}

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}


@shared_task(bind=True)
@log_execution
@requires_django_user_context
def industry_practices_subtask(self, prev_result, id, file_name, *args, **kwargs):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    file_path = get_absolute_file_path(request.file.name)

    # increment overall progress
    PROGRESS_INCREMENT = 10
    request.progress += PROGRESS_INCREMENT
    request.save()

    # add task
    task = ValidationTask.objects.create(request=request, type=ValidationTask.Type.INDUSTRY_PRACTICES)

    prev_result_succeeded = prev_result is not None and prev_result['is_valid'] is True
    if prev_result_succeeded:

        task.mark_as_initiated()

        # determine program/script to run
        check_script = os.path.join(os.path.dirname(__file__), "checks", "check_gherkin.py")
        check_program = [sys.executable, check_script, '--file-name', file_path, '--task-id', str(task.id), '--rule-type', 'INDUSTRY_PRACTICE']
        logger.debug(f'Command for {self.__qualname__}: {" ".join(check_program)}')

        # check Gherkin IP
        try:
            # note: use run instead of Popen b/c PIPE output can be very big...
            proc = subprocess.run(
                check_program,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=TASK_TIMEOUT_LIMIT
            )
            task.set_process_details(None, check_program)  # run() has no pid...

        except subprocess.TimeoutExpired as err:
            task.mark_as_failed(err)
            raise

        except Exception as err:
            task.mark_as_failed(err)
            raise

        if (proc.returncode is not None and proc.returncode != 0) or (len(proc.stderr) > 0):
            error_message = f"Running {' '.join(proc.args)} failed with exit code {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
            task.mark_as_failed(error_message)
            raise RuntimeError(error_message)

        raw_output = proc.stdout

        with transaction.atomic():

            # create or retrieve Model info
            model = get_or_create_ifc_model(id)

            # update Model info
            agg_status = task.determine_aggregate_status()
            model.status_industry_practices = agg_status
            model.save(update_fields=['status_industry_practices'])

            # update Task info and return
            is_valid = agg_status != Model.Status.INVALID
            reason = f'agg_status = {Model.Status(agg_status).label}\nraw_output = {raw_output}'
            task.mark_as_completed(reason)
            return {'is_valid': is_valid, 'reason': reason}

    else:
        reason = f'Skipped as prev_result = {prev_result}.'
        task.mark_as_skipped(reason)
        return {'is_valid': None, 'reason': reason}
