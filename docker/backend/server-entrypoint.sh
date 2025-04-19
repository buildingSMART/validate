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
python manage.py collectstatic --noinput

DJANGO_GUNICORN_WORKERS=${DJANGO_GUNICORN_WORKERS:-4} # default 4 workers
DJANGO_GUNICORN_THREADS_PER_WORKER=${DJANGO_GUNICORN_THREADS_PER_WORKER:-4} # default 4 threads

echo "Number of worker processes: $DJANGO_GUNICORN_WORKERS"
echo "Number of threads per worker: $DJANGO_GUNICORN_THREADS_PER_WORKER"

gunicorn core.wsgi --bind 0.0.0.0:8000 --workers $DJANGO_GUNICORN_WORKERS --threads $DJANGO_GUNICORN_THREADS_PER_WORKER --worker-class gevent --worker-tmp-dir /dev/shm --timeout 60 --keep-alive 60
