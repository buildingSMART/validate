from celery import shared_task
from celery.utils.log import get_task_logger
from django.template.loader import render_to_string

from core.utils import log_execution
from core.utils import send_email
from core.utils import get_title_from_html
from core.settings import PUBLIC_URL, ADMIN_EMAIL, CONTACT_EMAIL

from apps.ifc_validation_models.models import ValidationRequest

logger = get_task_logger(__name__)


def status_combine(*args):
    statuses = "-pvnwi"
    return statuses[max(map(statuses.index, args))]


@shared_task
@log_execution
def send_acknowledgement_user_email_task(id, file_name):

    # fetch request and user info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

   # load and merge email template
    merge_data = { 
        'FILE_NAME': file_name,
        'PUBLIC_URL': PUBLIC_URL
    }
    body_html = render_to_string("validation_ack_user_email.html", merge_data)
    body_text = f'Received request to validate file: {file_name}'
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(user.email, subject, body_text, body_html)
        return f'Sent acknowledgement email to {user.email}'
    except Warning as warn:
        return f'Warning - unable to send acknowledgement email to {user.email}: {warn}'
    except Exception as err:
        return f'Error - unable to send acknowledgement email to {user.email}: {err}'


@shared_task
@log_execution
def send_acknowledgement_admin_email_task(id, file_name):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'NUMBER_OF_FILES': 1,
        'FILE_NAMES': file_name,
        # From django docs: Returns the first_name plus the last_name, with a space in between.
        'USER_FULL_NAME': user.get_full_name(),
        'USER_EMAIL': user.email,
        'PUBLIC_URL': PUBLIC_URL
    }
    to = ADMIN_EMAIL
    body_html = render_to_string("validation_ack_admin_email.html", merge_data)
    body_text = f"User uploaded {{merge_data.NUMBER_OF_FILES}} file(s)."
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(to, subject, body_text, body_html)
        return f'Sent admin email to {to}'
    except Warning as warn:
        return f'Warning - unable to send admin email to {to}: {warn}'
    except Exception as err:
        return f'Error - unable to send admin email to {to}: {err}'
    

@shared_task
@log_execution
def send_revalidating_user_email_task(id, file_name):

    # fetch request and user info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'FILE_NAME': file_name,
        'FILE_DATE': request.created,
        'PUBLIC_URL': PUBLIC_URL
    }
    body_html = render_to_string("validation_reval_user_email.html", merge_data)
    body_text = f'Received request to revalidate file: {file_name}'
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(user.email, subject, body_text, body_html)
        return f'Sent reval acknowledgement email to {user.email}'
    except Warning as warn:
        return f'Warning - unable to send reval acknowledgement email to {user.email}: {warn}'
    except Exception as err:
        return f'Error - unable to send reval acknowledgement email to {user.email}: {err}'


@shared_task
@log_execution
def send_revalidating_admin_email_task(id, file_name):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'NUMBER_OF_FILES': 1,
        'FILE_NAMES': file_name,
        'USER_FULL_NAME': user.get_full_name(),
        'USER_EMAIL': user.email,
        'PUBLIC_URL': PUBLIC_URL
    }
    to = ADMIN_EMAIL
    body_html = render_to_string("validation_reval_admin_email.html", merge_data)
    body_text = f"Revalidating {{merge_data.NUMBER_OF_FILES}} file(s)."
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(to, subject, body_text, body_html)
        return f'Sent reval admin email to {to}'
    except Warning as warn:
        return f'Warning - unable to send reval admin email to {to}: {warn}'
    except Exception as err:
        return f'Error - unable to send reval admin email to {to}: {err}'
 

@shared_task
@log_execution
def send_completion_email_task(id, file_name):

    # fetch request and user info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'FILE_NAME': file_name,
        'ID': request.public_id,
        'STATUS_SYNTAX': ("p" if (request.model is None or request.model.status_syntax is None) else request.model.status_syntax) in ['v', 'w', 'i'],
        "STATUS_SCHEMA": status_combine(
            "p" if (request.model is None or request.model.status_schema is None) else request.model.status_schema,
            "p" if (request.model is None or request.model.status_prereq is None) else request.model.status_prereq
        ) in ['v', 'w', 'i'],
        "STATUS_BSDD": ("p" if (request.model is None or request.model.status_bsdd is None) else request.model.status_bsdd) in ['v', 'w', 'i'],
        "STATUS_RULES": status_combine(
            "p" if (request.model is None or request.model.status_ia is None) else request.model.status_ia,
            "p" if (request.model is None or request.model.status_ip is None)  else request.model.status_ip
        ) in ['v', 'w', 'i'],
        "STATUS_IND": ("p" if (request.model is None or request.model.status_industry_practices is None) else request.model.status_industry_practices) in ['v', 'w', 'i'],
        'PUBLIC_URL': PUBLIC_URL,
        'CONTACT_EMAIL': CONTACT_EMAIL
    }
    body_html = render_to_string("validation_completed_email.html", merge_data)
    body_text = f'Validation of file: {file_name} was completed.'
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(user.email, subject, body_text, body_html)
        return f'Sent completion email to {user.email}'
    except Warning as warn:
        return f'Warning - unable to send completion email to {user.email}: {warn}'
    except Exception as err:
        return f'Error - unable to send completion email to {user.email}: {err}'


@shared_task
@log_execution
def send_failure_email_task(id, file_name):

    # fetch request and user info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'FILE_NAME': file_name,
        'PUBLIC_URL': PUBLIC_URL,
        'CONTACT_EMAIL': CONTACT_EMAIL
    }
    body_html = render_to_string("validation_failed_email.html", merge_data)
    body_text = f'Unable to complete validation of file: {file_name}.'
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(user.email, subject, body_text, body_html)
        return f'Sent failure email to {user.email}'
    except Warning as warn:
        return f'Warning - unable to send failure email to {user.email}: {warn}'
    except Exception as err:
        return f'Error - unable to send failure email to {user.email}: {err}'
