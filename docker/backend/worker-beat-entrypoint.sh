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

echo "Waiting for DB on $POSTGRES_HOST:$POSTGRES_PORT..."
while ! python -c "import socket; s=socket.create_connection(('$POSTGRES_HOST', $POSTGRES_PORT), timeout=3); s.close()" 2>/dev/null
do
    echo "$POSTGRES_HOST:$POSTGRES_PORT - not yet available"
    sleep 5
done
echo "$POSTGRES_HOST:$POSTGRES_PORT - accepting connections"
echo "DB is ready."

# start clamav update & daemon
freshclam
service clamav-freshclam start
service clamav-daemon start

CELERY_CONCURRENCY=${CELERY_CONCURRENCY:-6} # default 6 worker processes
echo "Celery concurrency: $CELERY_CONCURRENCY"

celery --app=core worker --loglevel=info --concurrency $CELERY_CONCURRENCY --task-events --hostname=worker@%n --beat --scheduler django_celery_beat.schedulers:DatabaseScheduler