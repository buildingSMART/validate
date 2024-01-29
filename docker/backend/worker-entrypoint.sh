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

# run 10 workers + scheduler
celery --app=core worker --loglevel=info --concurrency 10 --task-events --hostname=worker1@%n --beat
# TODO - run as a daemon
# https://docs.celeryq.dev/en/latest/userguide/daemonizing.html#generic-init-scripts