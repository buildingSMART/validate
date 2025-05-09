.ONESHELL:

VIRTUAL_ENV = .dev/venv

none:
	@echo "MAKE: Enter at least one target (venv, install, install-dev, start-backend, start-worker, clean)"
	@echo

venv:
	test -d $(VIRTUAL_ENV) || python3.11 -m venv $(VIRTUAL_ENV)

install: venv
	. $(VIRTUAL_ENV)/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt && \
    wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.1-c49ca69-linux64.zip" && \
    mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages && \
    unzip -f -d $(VIRTUAL_ENV)/lib/python3.11/site-packages /tmp/ifcopenshell_python.zip && \
	rm /tmp/ifcopenshell_python.zip

install-macos: venv
	. $(VIRTUAL_ENV)/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt && \
	wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.1-c49ca69-macos64.zip" && \
	mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages && \
	unzip /tmp/ifcopenshell_python.zip -d .dev/venv/lib/python3.11/site-packages && \
	rm /tmp/ifcopenshell_python.zip

install-macos-m1: venv
	. $(VIRTUAL_ENV)/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt && \
	wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.8.1-c49ca69-macosm164.zip" && \
	mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages && \
	unzip /tmp/ifcopenshell_python.zip -d .dev/venv/lib/python3.11/site-packages && \
	rm /tmp/ifcopenshell_python.zip

fetch-modules:
	cd ./apps && \
	git submodule update --init --recursive

start-django: start-backend

start-backend:
	. $(VIRTUAL_ENV)/bin/activate && \
	python3 manage.py makemigrations && \
	python3 manage.py migrate && \
	python3 manage.py runserver

start-worker:
	. $(VIRTUAL_ENV)/bin/activate && \
	celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker@%n

start-worker2:
	. $(VIRTUAL_ENV)/bin/activate && \
	celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker2@%n

start-worker3:
	. $(VIRTUAL_ENV)/bin/activate && \
	celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker3@%n

start-worker4:
	. $(VIRTUAL_ENV)/bin/activate && \
	celery --app=core worker --loglevel=DEBUG --concurrency 2 --task-events --hostname=worker4@%n

start-worker-scheduler:
	. $(VIRTUAL_ENV)/bin/activate && \
	celery --app=core worker --loglevel=DEBUG --concurrency 5 --task-events --beat

test: test-models test-bsdd-task test-parse-info-task test-syntax-task test-schema-task

test-models:
	. $(VIRTUAL_ENV)/bin/activate && \
	MEDIA_ROOT=./apps/ifc_validation/fixtures python3 manage.py test apps/ifc_validation_models --settings apps.ifc_validation_models.test_settings --debug-mode --verbosity 3

test-bsdd-task:
	. $(VIRTUAL_ENV)/bin/activate && \
	MEDIA_ROOT=./apps/ifc_validation/fixtures python3 manage.py test apps.ifc_validation.tests.tests_bsdd_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-parse-info-task:
	. $(VIRTUAL_ENV)/bin/activate && \
	MEDIA_ROOT=./apps/ifc_validation/fixtures python3 manage.py test apps.ifc_validation.tests.tests_parse_info_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-syntax-task:
	. $(VIRTUAL_ENV)/bin/activate && \
	MEDIA_ROOT=./apps/ifc_validation/fixtures python3 manage.py test apps.ifc_validation.tests.tests_syntax_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

test-schema-task:
	. $(VIRTUAL_ENV)/bin/activate && \
	MEDIA_ROOT=./apps/ifc_validation/fixtures python3 manage.py test apps.ifc_validation.tests.tests_schema_validation_task --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

clean:
	rm -rf .dev
	rm -rf django_db.sqlite3
	rm -rf celery*.db
	rm -rf ".pytest_cache"
	find . -type d -name __pycache__  -prune -exec rm -rf {} \;

init-db:
	. $(VIRTUAL_ENV)/bin/activate && \
	PGPASSWORD=postgres psql -h localhost -U postgres --dbname postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" && \
	python3 manage.py makemigrations && \
	python3 manage.py migrate && \
	DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost python3 manage.py createsuperuser --noinput && \
	DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost python3 manage.py createsuperuser --noinput
