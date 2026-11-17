"""Isolated browser-test settings; never connect the parity suite to a user's DB."""
import os
from .test_settings import *  # noqa: F403

DEBUG = True
FRONTEND_MODE = os.environ.get("FRONTEND_MODE", "react")
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
INSTALLED_APPS = [*INSTALLED_APPS, "django.contrib.staticfiles"]  # noqa: F405
ROOT_URLCONF = "apps.ifc_validation_bff.tests.report_parity_urls"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:",
    "OPTIONS": {"transaction_mode": "IMMEDIATE"},
}}
MEDIA_ROOT = os.environ["REPORT_PARITY_MEDIA"]
MIDDLEWARE = [*MIDDLEWARE, "django.middleware.csrf.CsrfViewMiddleware"]  # noqa: F405
