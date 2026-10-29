#!/bin/bash
# Nightly refresh of the vs_adoption_capability fact table behind the
# "Implementer Adoption" Grafana dashboard. Runs the management command inside
# the running backend container, so it uses the service's own DB credentials.
#
# Cron on the MANAGER node, e.g.:
#   30 2 * * *  /home/prd-root/validation-service/docker/prometheus/prod-crons/refresh_adoption_metrics.sh
#
# Takes minutes, not seconds: one statement per month over the outcomes table.
# Exit code is the command's (1 if any month failed), so cron mail carries it.
set -uo pipefail

SERVICE=${SERVICE:-validate_backend}
MONTHS=${MONTHS:-13}

CID=$(docker ps --filter "name=${SERVICE}" --format '{{.ID}}' | head -1)
if [ -z "$CID" ]; then
    echo "refresh_adoption_metrics: no running container for service ${SERVICE}" >&2
    exit 1
fi

exec docker exec -w /app/backend "$CID" python manage.py refresh_adoption_metrics --months "$MONTHS"
