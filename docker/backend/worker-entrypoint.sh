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

python manage.py makemigrations
python manage.py migrate

CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-6} # default 6 worker processes
echo "Celery concurrency: $CELERY_CONCURRENCY"

celery --app=core worker --loglevel=info --concurrency $CELERY_CONCURRENCY --task-events --hostname=worker@%n --beat