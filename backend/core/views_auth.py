import json
import logging

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.utils import timezone
from requests.models import PreparedRequest

from authlib.integrations.django_client import OAuth

from .email_tasks import send_user_registered_admin_email_task
from .settings import LOGIN_CALLBACK_URL, POST_LOGIN_REDIRECT_URL, LOGOUT_URL, LOGIN_URL 
from .settings import USE_WHITELIST

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
    redirect_uri = LOGIN_CALLBACK_URL
    return oauth.b2c.authorize_redirect(request, redirect_uri)


def callback(request):
    err = request.GET.get('error') if request.method == "GET" else None
    if err:
        return HttpResponse(f'Authentication failed! Reason: <pre>{json.dumps(request.GET, indent = 4)}</pre>')
    token = oauth.b2c.authorize_access_token(request)
    
    userinfo = token['userinfo']
    request.session['user'] = userinfo

    username = userinfo['email'].lower()
    user = User.objects.all().filter(username=username).first()

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
    else:
        if user.is_active:
            user.last_login = timezone.now()
            user.save()

    return redirect(POST_LOGIN_REDIRECT_URL)


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
