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
    wget -O /tmp/ifcopenshell_python.zip "https://s3.amazonaws.com/ifcopenshell-builds/ifcopenshell-python-311-v0.7.0-742a9ec-linux64.zip" && \
    mkdir -p $(VIRTUAL_ENV)/lib/python3.11/site-packages && \
    unzip /tmp/ifcopenshell_python.zip -d $(VIRTUAL_ENV)/lib/python3.11/site-packages && \
	rm /tmp/ifcopenshell_python.zip

fetch-modules:
	cd ./apps && \
	git submodule update --init --recursive

start-django: fetch-modules start-backend

start-django-skip-fetch: start-backend

start-backend:
	. $(VIRTUAL_ENV)/bin/activate && \
	python3 manage.py makemigrations && \
	python3 manage.py migrate && \
	python3 manage.py runserver

IFC_VALIDATION_MODELS_DIR=apps/ifc_validation_models
IFC_GHERKIN_RULES_DIR=apps/ifc_validation/checks/ifc_gherkin_rules

SUBMODULE_IFC_VALIDATION_MODELS=ifc_validation_models
SUBMODULE_IFC_GHERKIN_RULES=ifc_gherkin_rules

# Update submodule and checkout specific branch
# e.g. 'make update-submodule submodule=ifc_gherkin_rules branch=development'
update-submodule:
	@if [ "$(submodule)" = "$(SUBMODULE_IFC_VALIDATION_MODELS)" ]; then \
		echo "Matches IFC Validation Models"; \
		eval SUBMODULE_DIR=$(IFC_VALIDATION_MODELS_DIR); \
	elif [ "$(submodule)" = "$(SUBMODULE_IFC_GHERKIN_RULES)" ]; then \
		echo "Matches IFC Gherkin Rules"; \
		eval SUBMODULE_DIR=$(IFC_GHERKIN_RULES_DIR); \
	else \
		echo "Unknown submodule '$(submodule)'. Please specify 'ifc_validation_models' or 'ifc_gherkin_rules'."; \
		exit 1; \
	fi; \
	cd $$SUBMODULE_DIR && git fetch; \
	if git show-ref --verify --quiet refs/heads/$(branch); then \
		git checkout $(branch) && git pull; \
	else \
		echo "else reached"; \
		git checkout $(branch) && git pull; \
	fi


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

test-models:
	. $(VIRTUAL_ENV)/bin/activate && \
	python3 manage.py test apps/ifc_validation_models --settings apps.ifc_validation_models.test_settings --debug-mode --verbosity 3

test-tasks:
	. $(VIRTUAL_ENV)/bin/activate && \
	MEDIA_ROOT=./apps/ifc_validation/fixtures python3 manage.py test apps.ifc_validation.tests_tasks --settings apps.ifc_validation.test_settings --debug-mode --verbosity 3

clean:
	rm -rf .dev
	rm -rf django_db.sqlite3
	rm -rf celery*.db
	rm -rf ".pytest_cache"
	find . -type d -name __pycache__  -prune -exec rm -rf {} \;

init-db:
	. $(VIRTUAL_ENV)/bin/activate && \
	PGPASSWORD=postgres psql -h localhost -U postgres --dbname postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" && \
	rm ./apps/ifc_validation_models/migrations/0001_initial.bak || true && \
	mv ./apps/ifc_validation_models/migrations/0001_initial.py ./apps/ifc_validation_models/migrations/0001_initial.bak || true && \
	rm ./apps/ifc_validation_models/migrations/0001_initial.bak || true && \
	python3 manage.py makemigrations && \
	python3 manage.py migrate && \
	DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost python3 manage.py createsuperuser --noinput && \
	DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost python3 manage.py createsuperuser --noinput