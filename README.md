# Software Infrastructure

![image](https://github.com/buildingSMART/validate/assets/155643707/5286c847-cf2a-478a-8940-fcdbd6fffeea)


# Application Structure

The application consists of two main submodules, each hosted in separate GitHub repositories. Docker Compose is configured to automatically bind the correct submodule versions for local deployment.

### Submodules

Documentation of the seperate functionalities can be found within each submodule.

1. **Gherkin Rules**: Contains the rules for validation. It can be run independently by cloning the repository and executing:
https://github.com/buildingSMART/ifc-gherkin-rules

   ```
   pytest -sv
   ```

   Debugging individual rules is supported with commands like:

   ``````
   python test/test_main.py alb001 # For a single rule
   python test/test_main.py alb001 alb002 # For multiple rules
   python test/test_main.py path_to_separate_file.py # For a separate file
   ``````

2. **Shared DataModel**: This module includes Django data models shared between the main repository and the Gherkin repository, serving as a submodule for both.
https://github.com/buildingSMART/ifc-validation-data-model

## Running Validation Checks

The application supports multiple validation checks on one or multiple IFC files that can be run separately:

- Syntax Check
- Schema Check
- Gherkin-Rules Check
- bSDD Check (disabled)

# How to start?

Depending on your workflow, you can run all or some services via Docker Compose.

Below are a few common options to run and debug these services locally.
More scenario's exist - have a look at the various *make* files.

## Option 1 - Run minimal set of services via Docker Compose (easiest to run)

1. Clone this repo in a local folder

```shell
mkdir bsi-validate
cd bsi-validate
git clone https://github.com/buildingSMART/validate
cd validate
git checkout <branch> # if not main
make fetch-modules
```

2. Make sure Docker is running.

```shell
docker info
```

3. Start all services.

```shell
make start
```
_or_ 
```
docker compose up
```

4. This pulls Docker-hub images, builds and spins up **five** different services:

```
db       - PostgreSQL database
redis    - Redis instance
backend  - Django Admin + API's
worker   - Celery worker
frontend - React UI
```

5. One-time only: create Django superuser accounts for Django Admin and Celery background worker(s), for example:

```shell
docker exec -it backend sh

cd backend

DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost python3 manage.py createsuperuser --noinput

DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost python3 manage.py createsuperuser --noinput

exit
```

6. Navigate to different services:

- Validation Service - React UI: http://localhost
- Django Admin UI: http://localhost/admin - default user/password per step 5.
- Django API - Swagger: http://localhost/api/swagger-ui
- Django API - Redoc: http://localhost/api/redoc

7. Optionally, use a tool like curl or Postman to invoke API requests directly

8. Restart services after pulling updates
----------------------------------------

```shell
# 1 — Stop running containers
make stop            # or: docker compose down

# 2 — Get the latest code
make checkout        # defaults to main
#       or: make checkout BRANCH=development

# 3 — Rebuild images (if Dockerfiles or base images changed) and start
docker compose up -d --build
```
   

## Option 2 - Local debugging + infrastructure via Docker Compose (easiest to debug)

1. Clone this repo in a local folder

```shell
mkdir bsi-validate
cd bsi-validate
git clone https://github.com/buildingSMART/validate 
cd validate 
git checkout <branch> # if not main
make fetch-modules
```

2. Make sure Docker is running.

```shell
docker info
```

3. Start infrastructure services only (Redis, Postgres, Celery Flower)

```shell
make start-infra
```
_or_
```
docker compose -f docker-compose.infra_only.yml up
```


4. This pulls different Docker-hub images and spins up **three** services:

```
db       - PostgreSQL database
redis    - Redis instance
flower   - Celery flower dashboard
```

5. Start Django backend (Admin + API)

```shell
cd backend
make install (or make install-macos/install-macos-m1)
make start-django
```

6. Start Celery worker(s)

```shell
cd backend
make start-worker
```

7. Start Node Development server to serve the React UI

```shell
cd frontend
npm install
npm run start
```

8. One-time only: create Django superuser accounts for Django Admin and Celery background worker(s), for example:

```shell
cd backend

. .dev/venv/bin/activate

DJANGO_SUPERUSER_USERNAME=root DJANGO_SUPERUSER_PASSWORD=root DJANGO_SUPERUSER_EMAIL=root@localhost python3 manage.py createsuperuser --noinput

DJANGO_SUPERUSER_USERNAME=SYSTEM DJANGO_SUPERUSER_PASSWORD=system DJANGO_SUPERUSER_EMAIL=system@localhost python3 manage.py createsuperuser --noinput
```

9. Navigate to different services:

- Validation Service - React UI: http://localhost:3000
- Django Admin UI: http://localhost:8000/admin - default user/password per step 8
- Django API - Swagger: http://localhost:8000/api/swagger-ui
- Django API - Redoc: http://localhost:8000/api/redoc
- Celery Flower UI: http://localhost:5555

10. Optionally, use a tool like curl or Postman to invoke API requests directly

11. Restart local services after code updates
---------------------------------------

If there are code changes (locally or from GitHub), restart the worker — and optionally the backend and frontend if they were stopped.

### 1. Stop running local services

- In the terminal running the backend or frontend: press `Ctrl+C`
- To stop the worker gracefully, run in a new terminal:

```shell
cd backend
make stop-worker
```
### 2. Update code (if pulling from github)
```shell
make fetch-modules && make checkout
```
### 3. Restart services 
```shell
cd backend
make start-worker
make start-backend
make start-frontend    
```


