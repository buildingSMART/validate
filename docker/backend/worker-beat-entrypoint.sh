#!/bin/sh
set -e # exit if any command fails

until cd /files_storage
do
    echo "Waiting for files_storage volume..."
done

until cd /app/backend
do
    echo "Waiting for server volume..."
done

while ! pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -d "$POSTGRES_NAME" -U "$POSTGRES_USER" 2>/dev/null
do
    echo "Waiting for DB to be ready..."
    sleep 5
done
echo "DB is ready."

# Beat-only: this service schedules periodic tasks and no longer consumes the
# celery queue itself. Task capacity lives in the worker service, where it is
# budgeted (resources.limits x CELERY_CONCURRENCY); the previous embedded worker
# added 4 unbudgeted task slots and peaked at 8 GB RSS without any memory limit.
celery --app=core beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler