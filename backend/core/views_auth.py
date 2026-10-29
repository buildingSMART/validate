import json
import logging
from urllib.parse import unquote

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.utils import timezone
from requests.models import PreparedRequest

from authlib.integrations.django_client import OAuth

from .email_tasks import send_user_registered_admin_email_task
from .settings import (
    LOGIN_CALLBACK_URL, 
    ADMIN_CALLBACK_URL, 
    POST_LOGIN_REDIRECT_URL,
    POST_ADMIN_LOGIN_REDIRECT_URL,
    LOGOUT_URL, 
    LOGIN_URL,
    USE_WHITELIST
)

oauth = OAuth()
oauth.register(name="b2c")
logger = logging.getLogger(__name__)


def whoami(request):
    user = request.session.get('user')
    if user:
        user = json.dumps(user, indent = 4)
        return HttpResponse(f'Welcome <pre>{user}</pre> You can <a href="{LOGOUT_URL}">logout here</a>.')
    else:
        return HttpResponse(f'Hello anonymous! Please <a href="{LOGIN_URL}">login</a>.')
    

def login(request):
    referer = request.headers.get('referer')
    django_admin = (referer and ('/admin' in referer or '/sqlexplorer' in referer))
    redirect_uri = ADMIN_CALLBACK_URL if django_admin else LOGIN_CALLBACK_URL
    state = json.dumps({ 
        'referer': referer, 
        'django_admin': django_admin 
    }) if referer else None
    return oauth.b2c.authorize_redirect(request, redirect_uri, state=state)


def callback(request):
    err = request.GET.get('error') if request.method == "GET" else None
    if err:
        return HttpResponse(f'Authentication failed! Reason: <pre>{json.dumps(request.GET, indent = 4)}</pre>')
    token = oauth.b2c.authorize_access_token(request)

    state = request.GET.get('state')
    if state:
        state = unquote(state)
        try:
            state = json.loads(state)
        except json.JSONDecodeError:
            pass
        request.session['oauth_state'] = state
        print(f'callback request state: {state}')
    
    userinfo = token['userinfo']
    request.session['user'] = userinfo

    username = userinfo['email'].lower()
    user = User.objects.all().filter(username__iexact=username).first()

    # create inactive user if not exist already
    if not user:

        with transaction.atomic():
            user = User.objects.create(
                username = username,
                password = username,
                email = userinfo['email'],
                is_active = not USE_WHITELIST, # whitelisting of users
                is_superuser = False,
                is_staff = False,
                first_name = userinfo['given_name'],
                last_name = userinfo['family_name']
            )

            transaction.on_commit(lambda: send_user_registered_admin_email_task.delay(user.id, user.email, user.is_active))
            logger.info(f"Created user with username = '{username}' via OAuth, user.id = {user.id}")

    django_admin = state['django_admin'] if state and 'django_admin' in state else False

    # redirect to frontend
    if user.is_active and not django_admin:
        auth_login(request, user)
        redirect_to = state['referer'] if state and 'referer' in state else POST_LOGIN_REDIRECT_URL
        logger.info(f"Logged into web app as user with username = '{username}' via OAuth, user.id = {user.id}")

    # redirect to django admin 
    elif user.is_active and django_admin:
        auth_login(request, user)
        redirect_to = state['referer'] if state and 'referer' in state else POST_ADMIN_LOGIN_REDIRECT_URL        
        logger.info(f"Logged into Django Admin as user with username = '{username}' via OAuth, user.id = {user.id}")

    # fallback
    else:        
        redirect_to = POST_LOGIN_REDIRECT_URL
        logger.warning(f"Logged in as user with username = '{username}' via OAuth, user.id = {user.id}")

    logger.info(f"Redirecting user with username = '{username}' to '{redirect_to}', user.id = {user.id}")
    return redirect(redirect_to)


def logout(request):
    request.session.pop('user', None)
    metadata = oauth.b2c.load_server_metadata()
    end_session_endpoint = metadata.get('end_session_endpoint')
    redirect_url = POST_LOGIN_REDIRECT_URL
    if end_session_endpoint:
        params = { 'post_logout_redirect_uri': request.build_absolute_uri('/') }
        req = PreparedRequest()
        req.prepare_url(end_session_endpoint, params)
        redirect_url = req.url
    return redirect(redirect_url)
