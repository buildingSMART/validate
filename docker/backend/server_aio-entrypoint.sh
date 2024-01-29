#!/bin/sh

until cd /files_storage
do
    echo "Waiting for files_storage volume..."
done

until cd /app/backend
do
    echo "Waiting for server volume..."
done

while ! nc -z db 5432
do
    echo "Waiting for DB to be ready..."
    sleep 3
done
echo "DB is ready."

# prepare Django 

python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic --noinput

# TODO - systemd vs supervisord vs deamon?

# run Django
gunicorn core.wsgi --bind 0.0.0.0:8000 --workers 4 --threads 4 --worker-class gevent --worker-tmp-dir /dev/shm

# run Celery worker + scheduler
celery --app=core worker --loglevel=info --concurrency 5 --task-events --hostname=worker1@%n --beat