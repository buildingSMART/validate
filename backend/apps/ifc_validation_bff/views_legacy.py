import operator
import os
import re
import json
from datetime import datetime
import logging
import itertools
import functools
import typing
from collections import defaultdict
import glob

from django.db import transaction
from django.db.models import Count
from django.http import JsonResponse, HttpResponse, FileResponse, HttpResponseNotFound, HttpResponseNotAllowed
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect

from apps.ifc_validation_models.models import IdObfuscator, ValidationOutcome, set_user_context
from apps.ifc_validation_models.models import ValidationRequest
from apps.ifc_validation_models.models import ValidationTask
from apps.ifc_validation_models.models import Model
from apps.ifc_validation_models.models import UserAdditionalInfo

from apps.ifc_validation.tasks import ifc_file_validation_task

from core.settings import MEDIA_ROOT, MAX_FILES_PER_UPLOAD
from core.settings import DEVELOPMENT, LOGIN_URL, USE_WHITELIST 
from core.settings import FEATURE_URL, MAX_OUTCOMES_PER_RULE

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
        user = UserAdditionalInfo.find_user_by_username(username)
       
        set_user_context(user)
        with transaction.atomic():
            uai, _ = UserAdditionalInfo.objects.get_or_create(user=user)
            company = UserAdditionalInfo.find_company_by_email_pattern(user)
            if company and (uai.company != company or not uai.is_vendor):
                logger.info(f"User with id={user.id} and email={user.email} matches email address pattern '{company.email_address_pattern}' of Company with id={company.id} ({company.name}).")
                uai.company = company
                uai.is_vendor = True
                uai.save()
                logger.info(f"User with id={user.id} and email={user.email} was assigned to Company with id={company.id} ({company.name}) and marked as 'is_vendor'.")

        logger.info(f"Authenticated user with username = '{username}' via OAuth, user.id = {user.id}")
        return user

    # only used for local development
    elif DEVELOPMENT and not USE_WHITELIST:

        username = 'development'
        user = UserAdditionalInfo.find_user_by_username(username)
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

        set_user_context(user)
        UserAdditionalInfo.objects.get_or_create(user=user)
        user = UserAdditionalInfo.find_user_by_username(username)

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


@functools.lru_cache(maxsize=1024)
def get_feature_filename(feature_code):
    """
    Retrieve the feature filename based on the feature_code (e.g. 'ALB005')
    """
    file_folder = os.path.dirname(os.path.realpath(__file__))
    rules_folder = os.path.join(file_folder, '../ifc_validation/checks/ifc_gherkin_rules/features/rules')
    return glob.glob(os.path.join(rules_folder, "**", f"{feature_code}*.feature"), recursive=True)


@functools.lru_cache(maxsize=1024)
def get_feature_url(feature_code):
    """
    Get the URL for the corresponding feature filename
    In DEV, we return the filename in the 'development' branch of the repository and 'main' for PROD. 
    """
    feature_files = get_feature_filename(feature_code)

    if feature_files:
        return os.path.join(FEATURE_URL, os.path.basename(feature_files[0].replace(".feature", ".html")))
    return None


@functools.lru_cache(maxsize=1024)
def get_feature_description(feature_code):
    feature_files = get_feature_filename(feature_code)
    if feature_files: 

        gherkin_desc = ''
        reading = False

        with open(feature_files[0], 'r', encoding='utf-8') as input_file:
            for line in input_file:
                if 'Feature:' in line:
                    reading = True
                if any(keyword in line for keyword in ['Scenario:', 'Background:', 'Scenario Outline:']):
                    return gherkin_desc
                if reading and line.strip() and 'Feature:' not in line and '@' not in line:
                    gherkin_desc += '\n' + line.strip()

    return None


def status_combine(*args, allow_not_executed=False):
    # status_header_syntax was introduced later and default initialized to `n`,
    # which has higher severity order in this logic than valid (`v`), we don't
    # want it to override the status for pre-existing data that never executed
    # this check.
    if allow_not_executed and not set(args) == {'n'}:
        args = [a for a in args if a != 'n']

    statuses = "-pvnwi"
    return statuses[max(map(statuses.index, args))]


def format_request(request : ValidationRequest):
    return {
        "id": request.public_id,
        "code": request.public_id,
        "filename": request.file_name,
        "file_date": None if request.model is None or request.model.date is None else datetime.strftime(request.model.date, '%Y-%m-%d %H:%M:%S'), # TODO - formatting is actually a UI concern...
        "user_id": IdObfuscator.to_public_id(request.created_by.id, override_cls=User),
        "progress": -2 if request.status == ValidationRequest.Status.FAILED else (-1 if request.status == ValidationRequest.Status.PENDING else request.progress),
        "date": datetime.strftime(request.created, '%Y-%m-%d %H:%M:%S'), # TODO - formatting is actually a UI concern...
        "license": '-' if (request.model is None or request.model.license is None) else request.model.license,
        "header_validation": None if (request.model is None or request.model.header_validation is None) else request.model.header_validation,
        "number_of_elements": None if (request.model is None or request.model.number_of_elements is None) else request.model.number_of_elements,
        "number_of_geometries": None if (request.model is None or request.model.number_of_geometries is None) else request.model.number_of_geometries,
        "number_of_properties": None if (request.model is None or request.model.number_of_properties is None) else request.model.number_of_properties,
        "authoring_application": '-' if (request.model is None or request.model.produced_by is None) else request.model.produced_by.name,
        "schema": '-' if (request.model is None or request.model.schema is None) else request.model.schema,
        "size": request.size,
        "mvd": '-' if (request.model is None or request.model.mvd is None) else request.model.mvd, # TODO - formatting is actually a UI concern...
        "status_syntax": status_combine(
            "p" if (request.model is None or request.model.status_syntax is None) else request.model.status_syntax,
            "p" if (request.model is None or request.model.status_header_syntax is None) else request.model.status_header_syntax,
            allow_not_executed=True
        ),
        "status_schema": status_combine(
            "p" if (request.model is None or request.model.status_schema is None) else request.model.status_schema,
            "p" if (request.model is None or request.model.status_prereq is None) else request.model.status_prereq
        ),
        "status_bsdd": "p" if (request.model is None or request.model.status_bsdd is None) else request.model.status_bsdd,
        "status_mvd": "p" if (request.model is None or request.model.status_mvd is None) else request.model.status_mvd,
        "status_ids": "p" if (request.model is None or request.model.status_ids is None) else request.model.status_ids,
        "status_header": "p" if (request.model is None or request.model.status_header is None) else request.model.status_header,
        "status_rules": status_combine(
            "p" if (request.model is None or request.model.status_ia is None) else request.model.status_ia,
            "p" if (request.model is None or request.model.status_ip is None)  else request.model.status_ip
        ),
        "status_ind": "p" if (request.model is None or request.model.status_industry_practices is None) else request.model.status_industry_practices,
        "status_signatures": "p" if (request.model is None or request.model.status_signatures is None) else request.model.status_signatures,
        "status_magic_clamav": "p" if (request.model is None or request.model.status_magic_clamav is None) else request.model.status_magic_clamav,
        "deleted": 0, # TODO
        "commit_id": None #  TODO
    }


#@login_required - doesn't work as OAuth is not integrated with Django
@ensure_csrf_cookie
@csrf_protect
def me(request):
    
    # return user or redirect response
    user = get_current_user(request)
    if user:

        # process self-declaration of vendor affiliation
        if request.method == "POST":

            data = json.loads(request.body)
            set_user_context(user)
            with transaction.atomic():
                uai, _ = UserAdditionalInfo.objects.get_or_create(user=user)
                uai.is_vendor_self_declared = data['is_vendor_self_declared']
                uai.save()
            user = get_current_user(request)

        json_response = {
            "user_data":
            {
                'sub': user.username,
                'email': user.email,
                'family_name': user.last_name,
                'given_name': user.first_name,
                'name': ' '.join([user.first_name, user.last_name]).strip(),
                'is_active': user.is_active,
                'is_vendor_self_declared': user.useradditionalinfo.is_vendor_self_declared if user.useradditionalinfo else None
            },
            "sandbox_info":
            {
                "pr_title": None,
                "commit_id": None
            },
            "redirect": None if user.is_active else '/waiting_zone'
        }
        return JsonResponse(json_response)
    
    else:
    
        return create_redirect_response(login=True)


@ensure_csrf_cookie
def models_paginated(request, start: int, end: int):

    if request.method != "GET":
        return HttpResponseNotAllowed()

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)
    
    # return model(s) as projection of Validation Request + Model attributes
    requests = ValidationRequest.objects.filter(created_by__id=user.id, deleted=False).order_by('-created')[start:end]
    total_count = ValidationRequest.objects.filter(created_by__id=user.id, deleted=False).count()
    models = list(map(format_request, requests))
    
    response_data = {}
    response_data['models'] = models
    response_data['count'] = total_count

    return JsonResponse(response_data)


@ensure_csrf_cookie
def download(request, id: int):

    if request.method != "GET":
        return HttpResponseNotAllowed()

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)

    logger.debug(f"Locating file for pub='{id}' pk='{ValidationRequest.to_private_id(id)}'")
    request = ValidationRequest.objects.filter(created_by__id=user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
    if request:
        file_path = os.path.join(os.path.abspath(MEDIA_ROOT), request.file.name)
        logger.debug(f"File to be downloaded is located at '{file_path}'")

        if request.file.name.endswith('.gz'):
            file_handle = open(file_path, 'rb')
            response = FileResponse(file_handle, content_type="application/gzip")
            response['Content-Length'] = os.path.getsize(file_path)
            logger.debug(f"Sending file with id='{id}' back as '{request.file_name}'")
        else:
            response = HttpResponse(open(file_path), content_type="application/x-step")        
            response['Content-Disposition'] = f'attachment; filename="{request.file_name}"'
            logger.debug(f"Sending file with id='{id}' back as '{request.file_name}'")

        return response
    else:
        logger.debug(f"Could not download file with id='{id}' for user.id='{user.id}' as it does not exist")
        return HttpResponseNotFound()


@ensure_csrf_cookie
@csrf_protect
def upload(request):

    if request.method != "POST":
        logger.error(f'Received invalid request: {request}')
        return HttpResponseNotAllowed()

    if request.method == "POST" and request.FILES:
        
        # fetch current user
        user = get_current_user(request)
        if not user:
            return create_redirect_response(login=True)
        if not user.is_active:
            return create_redirect_response(waiting_zone=True)
        
        set_user_context(user)

        referrer = request.headers["Referer"]
        if referrer is not None:
            if ("http://localhost" in referrer) or ("buildingsmart.org" in referrer):
                captured_channel = "WEBUI"
            else:
                captured_channel = "API"

        # parse files
        # can be POST-ed back as file or file[0] or files ...
        files = request.FILES.getlist('file')
        for i in range(0, MAX_FILES_PER_UPLOAD):
            file_i = request.FILES.getlist(f'file[{i}]', None)
            if file_i is not None: files += file_i
        logger.info(f"Received {len(files)} file(s) - files: {files}")

        # store and queue file for processing
        for f in files:
            with transaction.atomic():
                
                instance = ValidationRequest.objects.create(
                    file=f,
                    file_name=f.name,
                    size=f.size,
                    channel=captured_channel,
                )

                transaction.on_commit(lambda: ifc_file_validation_task.delay(instance.id, instance.file_name))    
                logger.info(f"Task 'ifc_file_validation_task' submitted for id: {instance.id} file_name: {instance.file_name} size: {f.size:,} bytes")

        # return to dashboard
        response = { 
            "url": "/dashboard"
        }
        return JsonResponse(response)

        #return HttpResponse(status=200) # TODO - this theoretically should be a 201_CREATED... 


@ensure_csrf_cookie
@csrf_protect
def delete(request, ids: str):

    if request.method != "DELETE":
        logger.error(f'Received invalid request: {request}')
        return HttpResponseNotAllowed()

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)
    
    set_user_context(user)

    if request.method == "DELETE" and len(ids.split(',')) > 0:

        with transaction.atomic():

            for id in ids.split(','):

                logger.info(f"Locating file for pub='{id}' pk='{ValidationRequest.to_private_id(id)}' and user.id='{user.id}'")
                request = ValidationRequest.objects.filter(created_by__id=user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()

                request.delete()
                logger.info(f"Validation Request with id='{id}' and related entities were marked as deleted.")

        # legacy API returns this object
        return JsonResponse({

            'status': 'success',
            'id': ids,
        })


@ensure_csrf_cookie
@csrf_protect
def revalidate(request, ids: str):

    if request.method != "POST":
        logger.error(f'Received invalid request: {request}')
        return HttpResponseNotAllowed()

     # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)
    
    set_user_context(user)

    with transaction.atomic():

        def on_commit(ids):

            for id in ids.split(','):
                request = ValidationRequest.objects.filter(created_by__id=user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
                ifc_file_validation_task.delay(request.id, request.file_name)
                logger.info(f"Task 'ifc_file_validation_task' re-submitted for Validation Request - id: {request.id} file_name: {request.file_name}")

        for id in ids.split(','):

            request = ValidationRequest.objects.filter(created_by__id=user.id, id=ValidationRequest.to_private_id(id)).first()
            request.mark_as_pending(reason='Resubmitted for processing via React UI')
            if request.model: request.model.reset_status()

        transaction.on_commit(lambda: on_commit(ids))      

    return JsonResponse({

        'status': 'success',
        'id': ids,
    })


@ensure_csrf_cookie
def report(request, id: str):

    if request.method != "GET":
        logger.error(f'Received invalid request: {request}')
        return HttpResponseNotAllowed()

    report_type = request.GET.get('type')
    
    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)

    # return 404-NotFound if report is not for current user or if it is deleted
    request = ValidationRequest.objects.filter(created_by__id=user.id, deleted=False, id=ValidationRequest.to_private_id(id)).first()
    if not request:
        return HttpResponseNotFound()
    
    # return file metrics as projection of Validation Request + Model attributes
    instances = {}
    model = format_request(request)
    
    # retrieve and map syntax outcome(s)
    syntax_results = []
    
    if report_type == "syntax" and request.model:
        if request.model.status_header_syntax == Model.Status.INVALID:
            failed_type = ValidationTask.Type.HEADER_SYNTAX
        elif request.model.status_syntax == Model.Status.INVALID:
            failed_type = ValidationTask.Type.SYNTAX
        else:
            failed_type = None                        

        if failed_type:
            logger.info('Fetching and mapping syntax results...')
            task = (ValidationTask.objects
                    .filter(request_id=request.id, type=failed_type)
                    .order_by("-id")   
                    .prefetch_related("outcomes")
                    .first())

            if task and task.outcomes:
                line_re = re.compile(r"^On line (\d+) column (\d+).*")
                for outcome in task.outcomes.all():
                    m = line_re.match(outcome.observed or "")
                    syntax_results.append({
                        "id": outcome.public_id,
                        "lineno": m.group(1) if m else None,
                        "column": m.group(2) if m else None,
                        "severity": outcome.severity,
                        "msg": f"expected: {outcome.expected}, observed: {outcome.observed}" if getattr(outcome, 'expected', None) is not None else outcome.observed,
                        "task_id": outcome.validation_task_public_id,
                    })
            logger.info('Fetching and mapping syntax done.')
    
    # retrieve and map schema outcome(s) + instances
    schema_results_count = defaultdict(int)
    schema_results = []
    if report_type == 'schema' and request.model:
        
        logger.info('Fetching and mapping schema results...')    
        
        task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.SCHEMA).last()
        if task.outcomes:
            for outcome in task.outcomes.order_by('-severity').iterator():

                mapped = {
                    "id": outcome.public_id,
                    "attribute": json.loads(outcome.feature)['attribute'] if outcome.feature else None, # eg. 'IfcSpatialStructureElement.WR41',
                    "constraint_type": json.loads(outcome.feature)['type'] if outcome.feature else None,  # 'uncategorized', 'schema', 'global_rule', 'simpletype_rule', 'entity_rule'
                    "instance_id": outcome.instance_public_id,
                    "severity": outcome.severity,
                    "msg": outcome.observed,
                    "task_id": outcome.validation_task_public_id
                }

                key = mapped.get('attribute', None) or 'Uncategorized'
                _type = mapped.get('constraint_type', None) or 'Uncategorized'
                title = _type.replace('_', ' ').capitalize() + ' - ' + key
                mapped['title'] = title # eg. 'Schema - SegmentStart'
                schema_results_count[title] += 1
                if schema_results_count[title] > MAX_OUTCOMES_PER_RULE:
                    continue
                
                schema_results.append(mapped)

                inst = outcome.instance
                if inst and inst.public_id not in instances:
                    instance = {
                        "guid": f'#{inst.stepfile_id}',
                        "type": inst.ifc_type
                    }
                    instances[inst.public_id] = instance
    
        logger.info('Fetching and mapping schema done.')

    # retrieve and map gherkin rules outcome(s) + instances
    grouping = (
        ('normative', (ValidationTask.Type.NORMATIVE_IA, ValidationTask.Type.NORMATIVE_IP)),
        ('prerequisites', (ValidationTask.Type.PREREQUISITES,)),
        ('industry', (ValidationTask.Type.INDUSTRY_PRACTICES,)))
    
    grouped_gherkin_outcomes_counts = { 
        'normative': defaultdict(int),
        'prerequisites': defaultdict(int),
        'industry': defaultdict(int)
    }
    grouped_gherkin_outcomes = {k: list() for k in map(operator.itemgetter(0), grouping)}

    for label, types in grouping:

        if not (report_type == label or (label == 'prerequisites' and report_type == 'schema')):
            continue

        logger.info(f'Fetching and mapping {label} gherkin results...')

        tasks = [ValidationTask.objects.filter(request_id=request.id, type=t).last() for t in types]
        all_features = itertools.chain.from_iterable([t.outcomes.values('feature').distinct().annotate(count=Count('feature')) for t in tasks])
        for item in all_features:

            feature = item.get('feature')
            count = item.get('count')

            # TODO: organize this differently?
            key = 'Schema - Version' if label == 'prerequisites' else feature
            grouped_gherkin_outcomes_counts[label][key] = count

            all_feature_outcomes : typing.Sequence[ValidationOutcome] = itertools.chain.from_iterable(
                t.outcomes.filter(feature=feature)
                 .prefetch_related("instance")                 
                 [:MAX_OUTCOMES_PER_RULE]
                 .iterator(chunk_size=100) for t in tasks)
                 
            for outcome in all_feature_outcomes:

                mapped = {
                    "id": outcome.public_id,
                    "title": key,
                    "feature": feature,
                    "feature_version": outcome.feature_version,
                    "feature_url": get_feature_url(outcome.feature[0:6]),
                    "feature_text": get_feature_description(outcome.feature[0:6]),
                    "step": outcome.get_severity_display(), # TODO
                    "severity": outcome.severity,
                    "instance_id": outcome.instance_public_id,
                    "expected": outcome.expected,
                    "observed": outcome.observed,
                    "message": str(outcome) if outcome.expected and outcome.observed else None,
                    "task_id": outcome.validation_task_public_id,
                    "msg": outcome.observed,
                }
                
                grouped_gherkin_outcomes[label].append(mapped)

                inst = outcome.instance
                if inst and inst.public_id not in instances:
                    instance = {
                        "guid": f'#{inst.stepfile_id}',
                        "type": inst.ifc_type
                    }
                    instances[inst.public_id] = instance

        logger.info(f'Mapped {label} gherkin results.')
        
    # retrieve and map bsdd results + instances
    bsdd_results = []
    if report_type == 'bsdd' and request.model:

        # bSDD is disabled > 404-NotFound
        logger.warning('Note: bSDD checks/reports are disabled.')
        return HttpResponseNotFound('bSDD checks are disabled')

        logger.info('Fetching and mapping bSDD results...')

        # only concerned about last run of each task
        task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.BSDD).last()
        if task.outcomes:
            for outcome in task.outcomes.iterator():
                feature_json = json.loads(outcome.feature)
                mapped = {
                    "id": outcome.id,                    
                    "severity": outcome.severity,
                    "instance_id": outcome.instance_id,
                    "expected": outcome.expected,
                    "observed": outcome.observed,
                    "category": feature_json['category'] if 'category' in feature_json else None,
                    "dictionary": feature_json['dictionary'] if 'dictionary' in feature_json else None,
                    "class": feature_json['class'] if 'class' in feature_json else None,
                    "task_id": outcome.validation_task_public_id,
                }
                bsdd_results.append(mapped)

                inst = outcome.instance
                if inst and inst.id not in instances:
                    instance = {
                        "guid": f'#{inst.stepfile_id}',
                        "type": inst.ifc_type
                    }
                    instances[inst.id] = instance

        logger.info('Fetching and mapping bSDD done.')

    signatures = []
    if report_type == "file":
        task = ValidationTask.objects.filter(request_id=request.id, type=ValidationTask.Type.DIGITAL_SIGNATURES).last()
        signatures = [t.observed for t in task.outcomes.iterator()] if task else None
        
    response_data = {
        'instances': instances,
        'model': model,
        'results': {
            "syntax_results": syntax_results,
            "schema": {
                "counts": [schema_results_count],
                "results": schema_results,
            },
            "bsdd_results": bsdd_results,
            "norm_rules": {
                "counts": grouped_gherkin_outcomes_counts["normative"],
                "results": grouped_gherkin_outcomes["normative"],
            },
            "ind_rules": {
                "counts": grouped_gherkin_outcomes_counts["industry"],
                "results": grouped_gherkin_outcomes["industry"],
            },
            "prereq_rules": {
                "counts": [grouped_gherkin_outcomes_counts["prerequisites"]],
                "results": grouped_gherkin_outcomes["prerequisites"]
            },
            "signatures": signatures
        }
    }

    logger.info('Serializing to JSON...')
    response = JsonResponse(response_data)
    logger.info('JSON done.')

    return response


@ensure_csrf_cookie
@csrf_protect
def report_error(request):

    if request.method != "POST":
        logger.error(f'Received invalid request: {request}')
        return HttpResponseNotAllowed()

    # fetch current user
    user = get_current_user(request)
    if not user:
        return create_redirect_response(login=True)

    # add to default log
    if request and hasattr(request, 'data'):
        error = request.data
        logger.info(f"Received error report: {error}")

    return HttpResponse(content='OK')
