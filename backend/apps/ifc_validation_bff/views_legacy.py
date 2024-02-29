import os, subprocess
import re
import json
from datetime import datetime
import logging
import itertools
import functools

from django.db import transaction
from django.core.files.storage import default_storage    
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseRedirect, HttpResponseNotFound
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from apps.ifc_validation_models.models import set_user_context
from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import Model

from apps.ifc_validation.tasks import ifc_file_validation_task

from core.settings import MEDIA_ROOT, DEVELOPMENT, LOGIN_URL

logger = logging.getLogger(__name__)

# IMPORTANT
#
# This view aims to be backwards compatible with the backend for the <0.6 UI
# It will be replaced with regular DRF-based views - hence some coding shortcuts


def get_current_user(request):

    # TODO - deeper integration with Django Auth/User model
    sso_user = request.session.get('user')
    if sso_user:
        
        username = sso_user['email'].lower()
        user = User.objects.all().filter(username=username).first()

        logger.info(f"Authenticated user with username = '{username}' via OAuth, user.id = {user.id}")
        return user
    
    elif DEVELOPMENT:

        username = 'development'
        user = User.objects.all().filter(username=username).first()
        if not user:
            user = User.objects.create(
                username = username,
                password = username,
                email = 'noreply@localhost',
                is_active = True, 
                is_superuser = True,
                is_staff = True,
                first_name = 'Dev',
                last_name = 'User'
            )
            logger.info(f"Created local DEV user, user = {user.id}")

        logger.info(f"Authenticated as local DEV, user = {user.id}")
        return user
    
    else:
        logger.info("Not authenticated")
        return None
    

def create_redirect_response(login=True, dashboard=False):

    if dashboard:

        return JsonResponse({
                "redirect": '/dashboard',
                "reason": "403 - Forbidden"
            })

    else:
        
        return JsonResponse({
                "redirect": LOGIN_URL,
                "reason": "401 - Unauthorized"
            })


@functools.lru_cache(maxsize=256)
def file_contains_string(file_name, fragment):

    with open(file_name, 'r') as file:
        for line_no, line in enumerate(file):
            if fragment in line:
                return True
    return False


@functools.lru_cache(maxsize=16)
def get_remote_base_url(folder):

    git_remote = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=folder).decode('ascii').split('\n')[0]
    git_blob = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=folder).decode('ascii').split('\n')[0]
    return f'{git_remote}/tree/{git_blob}'


@functools.lru_cache(maxsize=1024)
def get_feature_url(feature_code, feature_version):

    file_folder = os.path.dirname(os.path.realpath(__file__))
    feature_folder = os.path.join(file_folder, '../ifc_validation/checks/ifc_gherkin_rules/features')

    for file in os.listdir(feature_folder):
        file_name = os.fsdecode(file)
        fq_file_name = os.path.join(feature_folder, file_name)
        version_tag = f'@version{feature_version}'
        
        if file_name.endswith(".feature") and file_name.startswith(feature_code) and file_contains_string(fq_file_name, version_tag):
                return get_remote_base_url(feature_folder) + '/features/' + file_name
    
    return None


@functools.lru_cache(maxsize=1024)
def get_feature_description(feature_code, feature_version):

    # TODO - could probably use some of the ifc_gherkin_rules methods here?

    file_folder = os.path.dirname(os.path.realpath(__file__))
    feature_folder = os.path.join(file_folder, '../ifc_validation/checks/ifc_gherkin_rules/features')
    
    for file in os.listdir(feature_folder):
        file_name = os.fsdecode(file)
        fq_file_name = os.path.join(feature_folder, file_name)
        version_tag = f'@version{feature_version}'

        if file_name.endswith(".feature") and file_name.startswith(feature_code) and file_contains_string(fq_file_name, version_tag):
            
            gherkin_desc = ''
            reading = False

            with open(os.path.join(feature_folder, file_name), 'r') as input:
                
                for line in input:
                    if 'Feature:' in line:
                        reading = True
                    if 'Scenario:' in line or 'Background:' in line:
                        return gherkin_desc
                    if reading and len(line.strip()) > 0 and 'Feature:' not in line and '@' not in line: 
                        gherkin_desc += '\n' + line.strip()
    
    return None


#@login_required - doesn't work as OAuth is not integrated with Django
def me(request):
    
    # return user or redirect response
    user = get_current_user(request)
    if user:
        json = {
            "user_data":
            {
                'sub': user.username,
                'email': user.email,
                'family_name': user.last_name,
                'given_name': user.first_name,
                'name': ' '.join([user.first_name, user.last_name]).strip(),
                'is_active': user.is_active
            },
            "sandbox_info":
            {
                "pr_title": None,
                "commit_id": None
            },
            "redirect": None if user.is_active else '/waiting_zone'
        }
        return JsonResponse(json)
    
    else:
    
        return create_redirect_response(login=True)


def models_paginated(request, start: int, end: int):

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)
    
    # return model(s) as projection of Validation Request + Model attributes
    models = []
    requests = ValidationRequest.objects.filter(created_by__id=user.id).order_by('progress', '-updated')[start:end]
    total_count = ValidationRequest.objects.filter(created_by__id=user.id).count()
    for request in requests:
        models += [{
            "id": request.id,
            "code": request.id,  # TODO - not sure why another longer surrogate key was created?
            "filename": request.file_name,
            "file_date": None if request.model is None or request.model.date is None else datetime.strftime(request.model.date, '%Y-%m-%d %H:%M:%S'), # TODO - formatting is actually a UI concern...
            "user_id": request.created_by.id,
            "status": request.status,
            "progress": -2 if request.progress == ValidationRequest.Status.FAILED else (-1 if request.progress == ValidationRequest.Status.PENDING else request.progress),
            "date": (request.created if request.updated is None else request.updated).strftime("%Y-%m-%d %H:%M:%S"), # TODO - fix this, without formatting it crashes some browsers/users
            "number_of_elements": None if request.model is None else request.model.number_of_elements,
            "number_of_geometries": None if request.model is None else request.model.number_of_geometries,
            "number_of_properties": None if request.model is None else request.model.number_of_properties,
            "authoring_application": None if (request.model is None or request.model.produced_by is None) else request.model.produced_by.name,
            "status_syntax": "p" if (request.model is None or request.model.status_syntax is None) else request.model.status_syntax,
            "status_schema": "p" if (request.model is None or request.model.status_schema is None) else request.model.status_schema,
            "status_bsdd": "p" if (request.model is None or request.model.status_bsdd is None) else request.model.status_bsdd,
            "status_mvd": "p" if (request.model is None or request.model.status_mvd is None) else request.model.status_mvd,
            "status_ids": "p" if (request.model is None or request.model.status_ids is None) else request.model.status_ids,
            "status_ia": "p" if (request.model is None or request.model.status_ia is None) else request.model.status_ia,
            "status_ip": "p" if (request.model is None or request.model.status_ip is None)  else request.model.status_ip,
            "status_prereq": "p" if (request.model is None or request.model.status_prereq is None) else request.model.status_prereq,
            "status_ind": "p" if (request.model is None or request.model.status_industry_practices is None) else request.model.status_industry_practices,
        }]

    response_data = {}
    response_data['models'] = models
    response_data['count'] = total_count

    return JsonResponse(response_data)


def download(request, id: int):

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)

    logger.debug(f"Locating file for id='{id}'")
    request = ValidationRequest.objects.filter(created_by__id=user.id, id=id).first()
    if request:
        file_path = os.path.join(os.path.abspath(MEDIA_ROOT), request.file.name)
        logger.debug(f"File to be downloaded is located at '{file_path}'")

        response = HttpResponse(open(file_path), content_type="application/x-step")
        response['Content-Disposition'] = f'attachment; filename="{request.file_name}"'
        logger.debug(f"Sending file with id='{id}' back as '{request.file_name}'")

        return response
    else:
        logger.debug(f"Could not download file with id='{id}' for user.id='{user.id}' as it does not exist")
        return HttpResponseNotFound()


@csrf_exempt
def upload(request):

    if request.method == "POST" and request.FILES:
        
        # fetch current user
        user = get_current_user(request)
        if not user:
            return create_redirect_response(login=True)
        if not user.is_active:
            return create_redirect_response(waiting_zone=True)
        
        set_user_context(user)

        # parse files
        # can be POST-ed back as file or file[0] or files ...
        files = request.FILES.getlist('file')
        for i in range(0, 15):
            file_i = request.FILES.getlist(f'file[{i}]', None)
            if file_i is not None: files += file_i
        logger.info(f"Received {len(files)} file(s) - files: {files}")

        # store and queue file for processing
        for f in files:
            with transaction.atomic():
                abs_file_name = os.path.join(os.path.abspath(MEDIA_ROOT), f.name)
                path = default_storage.save(abs_file_name, ContentFile(f.read()))
                logger.info(f"{f.name} stored as '{path}' in {MEDIA_ROOT}")

                instance = ValidationRequest.objects.create(
                    file=f,
                    file_name=f.name,
                    size=os.path.getsize(abs_file_name)
                )

                transaction.on_commit(lambda: ifc_file_validation_task.delay(instance.id, instance.file_name))    
                logger.info(f"Task 'ifc_file_validation_task' submitted for id: {instance.id} file_name: {instance.file_name}")

        # return to dashboard
        response = { 
            "url": "/dashboard"
        }
        return JsonResponse(response)

        #return HttpResponse(status=200) # TODO - this theoretically should be a 201_CREATED... 
    else:
        logger.error(f'Received invalid request: {request}')
        return HttpResponseBadRequest()


# TODO currently a POST, should be a delete...
@csrf_exempt
def delete(request, ids: str):

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)

    with transaction.atomic():

        for id in ids.split(','):

            logger.info(f"Locating file for id='{id}' and user.id='{user.id}'")
            request = ValidationRequest.objects.filter(created_by__id=user.id, id=id).first()

            file_name = request.file_name
            file_absolute = os.path.join(MEDIA_ROOT, request.file.name)

            if os.path.exists(file_absolute):
                os.remove(file_absolute)
                logger.info(f"File '{file_name}' was deleted (physical file '{file_absolute}')")

            request.delete()
            logger.info(f"Validation Request with id='{id}' and related entities were deleted.")

    # legacy API returns this object
    return JsonResponse({

        'status': 'success',
        'id': ids,
    })


@csrf_exempt
def revalidate(request, ids: str):

     # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)
    
    set_user_context(user)

    with transaction.atomic():

        def on_commit(ids):

            for id in ids.split(','):
                request = ValidationRequest.objects.filter(created_by__id=user.id, id=id).first()
                ifc_file_validation_task.delay(request.id, request.file_name)
                logger.info(f"Task 'ifc_file_validation_task' re-submitted for Validation Request - id: {request.id} file_name: {request.file_name}")

        for id in ids.split(','):

            request = ValidationRequest.objects.filter(created_by__id=user.id, id=id).first()
            request.mark_as_pending(reason='Resubmitted for processing via React UI')
            if request.model: request.model.reset_status()

        transaction.on_commit(lambda: on_commit(ids))      

    return JsonResponse({

        'status': 'success',
        'id': ids,
    })


def report2(request, id: str):

    report_type = request.GET.get('type')
    
    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)

    # redirect if report is not for current user
    request = ValidationRequest.objects.filter(created_by__id=user.id, id=id).first()
    if not request:
        return create_redirect_response(dashboard=True)
    
    # return file metrics as projection of Validation Request + Model attributes
    instances = {}
    model = {
        "id": request.id,
        "code": request.id,  # TODO - not sure why another longer surrogate key was created?
        "filename": request.file_name,
        "file_date": None if request.model is None or request.model.date is None else datetime.strftime(request.model.date, '%Y-%m-%d %H:%M:%S'), # TODO - formatting is actually a UI concern...
        "user_id": request.created_by.id,
        "progress": request.progress,
        "date": datetime.strftime(request.created if request.updated is None else request.updated, '%Y-%m-%d %H:%M:%S'), # TODO - formatting is actually a UI concern...
        "license": request.model.license,
        "number_of_elements": None if (request.model is None or request.model.number_of_elements is None) else request.model.number_of_elements,
        "number_of_geometries": None if (request.model is None or request.model.number_of_geometries is None) else request.model.number_of_geometries,
        "number_of_properties": None if (request.model is None or request.model.number_of_properties is None) else request.model.number_of_properties,
        "authoring_application": None if (request.model is None or request.model.produced_by is None) else request.model.produced_by.name,
        "schema": request.model.schema,
        "size": request.size,
        "mvd": request.model.mvd,
        "status_syntax": "p" if (request.model is None or request.model.status_syntax is None) else request.model.status_syntax,
        "status_schema": "p" if (request.model is None or request.model.status_schema is None) else request.model.status_schema,
        "status_bsdd": "p" if (request.model is None or request.model.status_bsdd is None) else request.model.status_bsdd,
        "status_mvd": "p" if (request.model is None or request.model.status_mvd is None) else request.model.status_mvd,
        "status_ids": "p" if (request.model is None or request.model.status_ids is None) else request.model.status_ids,
        "status_ia": "p" if (request.model is None or request.model.status_ia is None) else request.model.status_ia,
        "status_ip": "p" if (request.model is None or request.model.status_ip is None)  else request.model.status_ip,
        "status_ind": "p" if (request.model is None or request.model.status_industry_practices is None) else request.model.status_industry_practices,
        "status_prereq": "p" if (request.model is None or request.model.status_prereq is None) else request.model.status_prereq,
        "deleted": 0, # TODO
        "commit_id": None #  TODO
    }
    
    # retrieve and map syntax outcome(s)
    syntax_results = []
    if report_type == 'syntax' and request.model and request.model.status_syntax != Model.Status.VALID:
        
        logger.info('Fetching and mapping syntax results...')    
        
        task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.SYNTAX).last()
        if task.outcomes:
            for outcome in task.outcomes.iterator():

                # TODO - should we not do this in the model?
                match = re.search('^On line ([0-9])+ column ([0-9])+(.)*', outcome.observed)                
                mapped = {
                    "id": outcome.id,
                    "lineno": match.groups()[0] if match and len(match.groups()) > 0 else None,
                    "column": match.groups()[1] if match and len(match.groups()) > 1 else None,
                    "severity": outcome.severity,
                    "msg": outcome.observed,
                    "task_id": outcome.validation_task_id
                }
                syntax_results.append(mapped)
    
        logger.info('Fetching and mapping syntax done.')

    # retrieve and map schema outcome(s) + instances
    schema_results = []
    if report_type == 'schema' and request.model:
        
        logger.info('Fetching and mapping schema results...')    
        
        # only concerned about last run of each task
        task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.SCHEMA).last()
        if task.outcomes:
            for outcome in task.outcomes.iterator():
                mapped = {
                    "id": outcome.id,
                    "attribute": json.loads(outcome.feature)['attribute'], # eg. 'IfcSpatialStructureElement.WR41',
                    "constraint_type": json.loads(outcome.feature)['type'],  # 'uncategorized', 'schema', 'global_rule', 'simpletype_rule', 'entity_rule'
                    "instance_id": outcome.instance_id,
                    "severity": outcome.severity,
                    "msg": outcome.observed,
                    "task_id": outcome.validation_task_id
                }
                schema_results.append(mapped)

                inst = outcome.instance
                if inst and inst.id not in instances:
                    instance = {
                        "guid": f'#{inst.stepfile_id}',
                        "type": inst.ifc_type
                    }
                    instances[inst.id] = instance
    
        logger.info('Fetching and mapping schema done.')

    # retrieve and map normative gherkin results + instances   
    gherkin_norm_results = []
    if report_type == 'normative' and request.model:

        logger.info('Fetching and mapping Normative Rules Gherkin results...')

        ia_task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.NORMATIVE_IA).last()
        ip_task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.NORMATIVE_IP).last()
        pre_task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.PREREQUISITES).last()
        normative_outcomes = itertools.chain(ia_task.outcomes.iterator(), ip_task.outcomes.iterator(), pre_task.outcomes.iterator())
        
        for outcome in normative_outcomes:
            mapped = {                
                "id": outcome.id,
                "feature": outcome.feature,
                "feature_version": outcome.feature_version,
                "feature_url": get_feature_url(outcome.feature[0:6], outcome.feature_version),
                "feature_text": get_feature_description(outcome.feature[0:6], outcome.feature_version),
                "step": outcome.get_severity_display(), # TODO
                "severity": outcome.severity,
                "instance_id": outcome.instance_id,
                "expected": outcome.expected,
                "observed": outcome.observed,
                "message": str(outcome) if outcome.expected and outcome.observed else None,
                "task_id": outcome.validation_task_id,
                "msg": outcome.observed,                    
            }
            gherkin_norm_results.append(mapped)

            inst = outcome.instance
            if inst and inst.id not in instances:
                instance = {
                    "guid": f'#{inst.stepfile_id}',
                    "type": inst.ifc_type
                }
                instances[inst.id] = instance
        
        logger.info('Mapped Normative Rules Gherkin.')

    # retrieve and map industry gherkin results + instances   
    gherkin_ind_results = []
    if report_type == 'industry' and request.model:

        logger.info('Fetching and mapping Industry Practices Gherkin results...')

        ind_task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.INDUSTRY_PRACTICES).last()
        ind_outcomes = ind_task.outcomes.iterator()

        for outcome in ind_outcomes:

            mapped = {                
                "id": outcome.id,
                "feature": outcome.feature,
                "feature_version": outcome.feature_version,
                "feature_url": get_feature_url(outcome.feature[0:6], outcome.feature_version),
                "feature_text": get_feature_description(outcome.feature[0:6], outcome.feature_version),
                "step": outcome.get_severity_display(), # TODO
                "severity": outcome.severity,
                "instance_id": outcome.instance_id,
                "expected": outcome.expected,
                "observed": outcome.observed,
                "message": str(outcome),
                "task_id": outcome.validation_task_id,
                "msg": outcome.observed,                    
            }
            gherkin_ind_results.append(mapped)
            
            inst = outcome.instance
            if inst and inst.id not in instances:
                instance = {
                    "guid": f'#{inst.stepfile_id}',
                    "type": inst.ifc_type
                }
                instances[inst.id] = instance

        logger.info('Mapped Industry Practices Gherkin results.')
    
    # retrieve and map bsdd results + instances
    bsdd_results = []
    if report_type == 'bsdd' and request.model:
        
        # TODO
        pass

    response_data = {
        'instances': instances,
        'model': model,
        'results': {
            "syntax_results": syntax_results,
            "schema_results": schema_results,
            "bsdd_results": bsdd_results,
            "norm_rules_results": gherkin_norm_results,
            "ind_rules_results": gherkin_ind_results,
        }
    }

    logger.info('Serializing to JSON...')
    response = JsonResponse(response_data)
    logger.info('JSON done.')

    return response


def report_error(request, path):

    # TODO
    return HttpResponse(content='OK')
