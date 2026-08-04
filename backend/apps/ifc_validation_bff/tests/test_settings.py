import os
from dotenv import load_dotenv

load_dotenv()

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "apps.ifc_validation",
    "apps.ifc_validation_models",
    "apps.ifc_validation_bff",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "apps.ifc_validation_bff.urls"

DB_SQLITE = "sqlite"

DATABASES_ALL = {
    DB_SQLITE: {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "test_django_db.sqlite3",
        "MIGRATE": False,
    }
}

DATABASES = {"default": DATABASES_ALL[os.environ.get("TEST_DJANGO_DB", DB_SQLITE)]}

MEDIA_ROOT = "./apps/ifc_validation/fixtures"
USE_TZ = True
SECRET_KEY = "insecure-test-only-secret-key"
