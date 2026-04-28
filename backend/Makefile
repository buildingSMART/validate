.ONESHELL:

VIRTUAL_ENV = .dev/venv
PYTHON = $(VIRTUAL_ENV)/bin/python
PIP = $(VIRTUAL_ENV)/bin/pip 

none:
	@echo "MAKE: Enter at least one target (venv, install, install-dev, start-backend, start-worker, clean)"
	@echo

venv:
	test -d $(VIRTUAL_ENV) || python3.11 -m venv $(VIRTUAL_ENV) 

install: venv
	$(PIP) install --upgrade pip
	find . -name 'requirements.txt' -exec $(PIP) install -r {} \;
	wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.5-a51b2c5-linux64.zip"
	mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages
	unzip -f -d $(VIRTUAL_ENV)/lib/python3.11/site-packages /tmp/ifcopenshell_python.zip
	rm /tmp/ifcopenshell_python.zip

install-macos: venv
	find . -name 'requirements.txt' -exec $(PIP) install -r {} \;
	$(PIP) install -r requirements.txt
	wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.5-1c5b825-macos64.zip"
	mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages
	unzip /tmp/ifcopenshell_python.zip -d $(VIRTUAL_ENV)/lib/python3.11/site-packages
	rm /tmp/ifcopenshell_python.zip

install-macos-m1: venv
	find . -name 'requirements.txt' -exec $(PIP) install -r {} \;
	$(PIP) install -r requirements.txt
	wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.5-1c5b825-macosm164.zip"
	mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages
	unzip /tmp/ifcopenshell_python.zip -d $(VIRTUAL_ENV)/lib/python3.11/site-packages
	rm /tmp/ifcopenshell_python.zip

fetch-modules:
	cd ./apps && git submodule update --init --recursive

start-django: start-backend

start-backend:
	$(PYTHON) manage.py makemigrations
	$(PYTHON) manage.py migrate
	$(PYTHON) manage.py collectstatic --noinput
	$(PYTHON) manage.py runserver

start-worker:
	$(PYTHON) -m celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker@%n

start-worker-with-scheduler:
	$(PYTHON) -m celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker@%n --beat --scheduler django_celery_beat.schedulers:DatabaseScheduler

start-worker2:
	$(PYTHON) -m celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker2@%n

start-worker3:
	$(PYTHON) -m celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker3@%n

start-worker4:
	$(PYTHON) -m celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker4@%n

.PHONY: stop-worker
stop-worker:
	-$(PYTHON) -m celery -A core control shutdown \
	    --destination=worker@$(shell hostname) || true

test: test-models test-header-validation-task test-syntax-task test-syntax-header-validation-task test-schema-task test-magic-and-av-task test-utils

test-models:
	MEDIA_ROOT=./apps/ifc_validation/fixtures $(PYTHON) manage.py test apps/ifc_validation_models --settings apps.ifc_validation_models.test_settings --debug-mode --verbosity 3

test-syntax-header-validation-task:
	MEDIA_ROOT=./apps/ifc_validation/fixtures $(PYTHON) manage.py test apps.ifc_validation.tests.tests_header_syntax_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-header-validation-task:
	MEDIA_ROOT=./apps/ifc_validation/fixtures $(PYTHON) manage.py test apps.ifc_validation.tests.tests_header_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-syntax-task:
	MEDIA_ROOT=./apps/ifc_validation/fixtures $(PYTHON) manage.py test apps.ifc_validation.tests.tests_header_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-schema-task:
	MEDIA_ROOT=./apps/ifc_validation/fixtures $(PYTHON) manage.py test apps.ifc_validation.tests.tests_schema_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-magic-and-av-task:
	MEDIA_ROOT=./apps/ifc_validation/fixtures $(PYTHON) manage.py test apps.ifc_validation.tests.tests_magic_clamav_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-utils:
	$(PYTHON) manage.py test core.tests.test_utils --debug-mode --verbosity 3

archive-files:
	$(PYTHON) manage.py archive_files --days 90 --all --dry-run

archive-files-confirm:
	$(PYTHON) manage.py archive_files --days 90 --all --confirm

remove-files:
	$(PYTHON) manage.py remove_files --days 180 --all --dry-run

remove-files-confirm:
	$(PYTHON) manage.py remove_files --days 180 --all --confirm

clean:
	rm -rf .dev
	rm -rf django_db.sqlite3
	rm -rf celery*.db
	rm -rf ".pytest_cache"
	find . -type d -name __pycache__  -prune -exec rm -rf {} \;

init-db:
	PGPASSWORD=postgres psql -h localhost -U postgres --dbname postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	$(PYTHON) manage.py makemigrations
	$(PYTHON) manage.py migrate
	DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost $(PYTHON) manage.py createsuperuser --noinput
	DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost $(PYTHON) manage.py createsuperuser --noinput
