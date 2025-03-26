#!/bin/sh

until cd /files_storage
do
    echo "Waiting for files_storage volume..."
done

until cd /app/backend
do
    echo "Waiting for server volume..."
done

while ! nc -z ${POSTGRES_HOST} ${POSTGRES_PORT}
do
    echo "Waiting for DB to be ready..."
    sleep 3
done
echo "DB is ready."

python manage.py makemigrations
python manage.py migrate
if [ $? -ne 0 ]; then  
    echo "Error: Failed to run Django Migrations."
    exit 1
fi

CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-6} # default 6 worker processes
echo "Celery concurrency: $CELERY_CONCURRENCY"

celery --app=core worker --loglevel=info --concurrency $CELERY_CONCURRENCY --task-events --hostname=worker@%n --beat