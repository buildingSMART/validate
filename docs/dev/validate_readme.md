
# Application Structure

## System Architecture

```{image} ../_static/dev_system_architecture_sketch.png
:alt: System Architure
:align: center
```

The Validation Service is built on [django](https://www.djangoproject.com),
using [Postgres](https://www.postgresql.org) as the database,
[Redis](https://www.redis.io) for task management,
and [Celery](https://docs.celeryq.dev/en/stable/index.html) for distributing the work of running the validation tasks.
The service consists of multiple containers managed with Docker compose.

## Submodules

The application consists of three main submodules, each hosted in separate GitHub repositories. Docker Compose is configured to automatically bind the correct submodule versions for local deployment.

Documentation of the separate functionalities can be found within each submodule.

1. **File Parser**: A [module within IfcOpenShell](https://github.com/IfcOpenShell/step-file-parser), dedicated to parsing files. 
2. **Gherkin Rules**: Contains the rules for validation. It can be run independently by cloning the [repository](https://github.com/buildingSMART/ifc-gherkin-rules) and executing:

   ```shell
   pytest -sv
   ```

   Debugging individual rules is supported with commands like:

   ``````shell
   python test/test_main.py alb001 # For a single rule
   python test/test_main.py alb001 alb002 # For multiple rules
   python test/test_main.py path_to_separate_file.py # For a separate file
   ``````

3. **Shared DataModel**: This [module](https://github.com/buildingSMART/ifc-validation-data-model) includes Django data models shared between the main repository and the Gherkin repository,
serving as a submodule for both.

## Running Validation Checks

The application supports multiple validation checks on one or multiple IFC files that can be run separately:

- Syntax Check
- Schema Check
- Normative Rules (gherkin) Check
- bSDD Check

# How to start?

Depending on your workflow, you can run all or some services via Docker Compose.

Below are a few common options to run and debug these services locally.
More scenario's exist - have a look at the various *make* files.

## Option 1 - Run minimal set of services via Docker Compose (easiest to run)

1. Make sure Docker is running.

2. Start all services.

```shell
make start

or 

docker compose up
```

3. This pulls Docker-hub images, builds and spins up **six** different services:

```
db       - PostgreSQL database
redis    - Redis instance
backend  - Django Admin + API's
worker   - Celery worker
flower   - Celery flower dashboard
frontend - React UI
```

4. One-time only: create Django superuser accounts for Django Admin and Celery background worker(s), for example:

```shell
docker exec -it backend sh

cd backend

DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost python3 manage.py createsuperuser --noinput

DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost python3 manage.py createsuperuser --noinput

exit
```

5. Navigate to different services:

- Validation Service - React UI: http://localhost
- Django Admin UI: http://localhost/admin (or http://localhost:8000/admin) - default user/password: root/root
- Django API - Swagger: http://localhost/api/swagger-ui
- Django API - Redoc: http://localhost/api/redoc
- Celery Flower UI: http://localhost:5555

6. Optionally, use a tool like curl or Postman to invoke API requests directly

## Option 2 - Local debugging + infrastructure via Docker Compose (easiest to debug)

1. Make sure Docker is running.

2. Start infrastructure services only (Redis, Postgres, Celery Flower)

```shell
make start-infra

or

docker compose -f docker-compose.infra_only.yml up
```


3. This pulls **three** different Docker-hub images and spins up  services:

```
db       - PostgreSQL database
redis    - Redis instance
flower   - Celery flower dashboard
```

4. Start Django backend (Admin + API)

```shell
cd backend
make install
make start-django
```

5. Start Celery worker(s)

```shell
cd backend
make start-worker
```

6. Start Node Development server to serve the React UI

```shell
cd frontend
npm install
npm run start
```

7. One-time only: create Django superuser accounts for Django Admin and Celery background worker(s), for example:

```shell
cd backend

DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost python3 manage.py createsuperuser --noinput

DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost python3 manage.py createsuperuser --noinput
```

8. Navigate to different services:

- Validation Service - React UI: http://localhost:3000
- Django Admin UI: http://localhost:8000/admin - default user/password: root/root
- Django API - Swagger: http://localhost:8000/api/swagger-ui
- Django API - Redoc: http://localhost:8000/api/redoc
- Celery Flower UI: http://localhost:5555

9. Optionally, use a tool like curl or Postman to invoke API requests directly