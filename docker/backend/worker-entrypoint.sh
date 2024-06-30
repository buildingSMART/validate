#!/bin/sh

until cd /files_storage
do
    echo "Waiting for files_storage volume..."
done

until cd /app/backend
do
    echo "Waiting for server volume..."
done

CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-6} # default 6 worker processes
echo "Celery concurrency: $CELERY_CONCURRENCY"

celery --app=core worker --loglevel=info --concurrency $CELERY_CONCURRENCY --task-events --hostname=worker@%n --beat