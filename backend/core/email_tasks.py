from celery import shared_task
from celery.utils.log import get_task_logger
from django.template.loader import render_to_string

from .utils import log_execution
from .utils import send_email
from .utils import get_title_from_html
from .settings import PUBLIC_URL, ADMIN_EMAIL

logger = get_task_logger(__name__)


@shared_task
@log_execution
def send_user_registered_admin_email_task(user_id, user_email, is_active = True):

    # load and merge email template
    merge_data = { 
        'USER_ID': user_id,
        'USER_EMAIL': user_email,
        'IS_ACTIVE': is_active,
        'PUBLIC_URL': PUBLIC_URL,
        'ACTIVATE_URL': PUBLIC_URL + '/admin/auth/user'
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