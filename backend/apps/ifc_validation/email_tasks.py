import os
import re

from celery import shared_task
from celery.utils.log import get_task_logger
from django.template.loader import render_to_string

from core.utils import log_execution
from core.utils import send_email

from apps.ifc_validation_models.decorators import requires_django_user_context
from apps.ifc_validation_models.models import ValidationRequest

logger = get_task_logger(__name__)

PUBLIC_URL = os.getenv('PUBLIC_URL').strip('/') if os.getenv('PUBLIC_URL') is not None else None
CONTACT_EMAIL = os.getenv('CONTACT_EMAIL', 'noreply@localhost')  # who to contact with questions/comments
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'noreply@localhost')      # who receives admin-style notifications


def get_title_from_html(body_html):
    """
    Parses a HTML document and returns the contents of the first <title> tag.
    """
    return re.findall(r'<title>(.*?)<\/title>', body_html)[0]


@shared_task
@log_execution
@requires_django_user_context
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
@requires_django_user_context
def send_acknowledgement_admin_email_task(id, file_name):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'NUMBER_OF_FILES': 1,
        'FILE_NAMES': file_name,
        'USER_NAME': user.username,
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
@requires_django_user_context
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
@requires_django_user_context
def send_revalidating_admin_email_task(id, file_name):

    # fetch request info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'NUMBER_OF_FILES': 1,
        'FILE_NAMES': file_name,
        'USER_NAME': user.username,
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
@requires_django_user_context
def send_completion_email_task(id, file_name):

    # fetch request and user info
    request = ValidationRequest.objects.get(pk=id)
    user = request.created_by

    # load and merge email template
    merge_data = { 
        'FILE_NAME': file_name,
        'ID': id,
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
@requires_django_user_context
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


@shared_task
@log_execution
@requires_django_user_context
def send_user_registered_admin_email_task(user_id, user_email):

    # load and merge email template
    merge_data = { 
        'USER_ID': user_id,
        'USER_EMAIL': user_email,
        'PUBLIC_URL': PUBLIC_URL
    }
    to = ADMIN_EMAIL
    body_html = render_to_string("user_registered_admin_email.html", merge_data)
    body_text = f"User {{user_email}} registered for the Validation Service."
    subject = get_title_from_html(body_html)

    # queue for sending
    try:
        send_email(to, subject, body_text, body_html)
        return f'Sent user registration admin email to {to}'
    except Warning as warn:
        return f'Warning - unable to send user registration admin email to {to}: {warn}'
    except Exception as err:
        return f'Error - unable to send user registration admin email to {to}: {err}'