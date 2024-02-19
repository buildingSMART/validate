import os
import math
import requests
import functools
import logging

logger = logging.getLogger()


def get_client_ip_address(request):

    """
    Returns the real end-user IP address, based on HTTP headers of a request.
    """

    req_headers = request.META
    x_forwarded_for_value = req_headers.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for_value:
        ip_addr = x_forwarded_for_value.split(',')[-1].strip()
    else:
        ip_addr = req_headers.get('REMOTE_ADDR')

    return ip_addr


def format_human_readable_file_size(file_size):

    """
    Returns a more human-readable string representation of a file size.

    Args:
        file_size (int): file size in bytes

    Returns:
        str: Human-readable file size (eg. 15 kB)
    """

    if file_size is None:
        return None
    
    if file_size == 0:
       return "0 B"
   
    size_name = ("B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(file_size, 1024)))
    p = math.pow(1024, i)
    s = round(file_size / p, 2)

    return f"{s} {size_name[i]}"


def log_execution(func):

    """
    Logs execution of a function (arguments and result).
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        logger.debug(f"Function {func.__name__}() called with args {signature}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"Function {func.__name__}() returned result {result}")
            return result

        # Celery uses Ignore to pass status; not really an exception
        # except Ignore:
        #     raise

        except Exception as err:
            logger.exception(f"Exception raised in {func.__name__}() - Exception: {str(err)}")
            raise

    return wrapper


def send_email(to, subject, body_text, body_html=None):

    """
    Queues an email for sending via the configured email provider (Mailgun only for now).
    Configured via OS environment variables or .env file.
    """

    # load configuration
    MAILGUN_API_URL = os.getenv('MAILGUN_API_URL', None)
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY', None)
    MAILGUN_FROM_NAME = os.getenv('MAILGUN_FROM_NAME', None)
    MAILGUN_FROM_EMAIL = os.getenv('MAILGUN_FROM_EMAIL', None)

    # check configuration
    for param in ['MAILGUN_API_URL', 'MAILGUN_API_KEY', 'MAILGUN_FROM_NAME', 'MAILGUN_FROM_EMAIL']:
        if eval(param) is None:
            message = f"Incomplete email configuration; '{param}' is missing."
            logger.error(message)
            raise RuntimeError(message)

    # split potential multiple 'to' addresses
    email_addresses = to.split(';')
    email_addresses = [s.strip() for s in email_addresses]
    
    for email in email_addresses:

        # only send if email address has a valid public TLD
        email_domain = email.split('@')[1]
        if email_domain in ['localhost', '127.0.0.1']:
            message = f"Email address '{email}' does not have a valid public TLD - skipped actual sending of message '{subject}'."
            logger.warning(message)
            raise RuntimeWarning(message)
        
        # invoke Mailgun API    
        response = requests.post(
            MAILGUN_API_URL,
            auth= ("api", MAILGUN_API_KEY),
            data= { 
                "from": f"{MAILGUN_FROM_NAME} <{MAILGUN_FROM_EMAIL}>",
                "to": email,
                "subject": subject,
                "text": body_text,
                "html": body_html
            })
        response.raise_for_status()
        logger.debug(f"Sent email to '{email}' with subject '{subject}'")
