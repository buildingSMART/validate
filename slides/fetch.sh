#!/usr/bin/env bash
#
# Fetch JSON query results from the deployed validation service into data/.
#
# Override the connection defaults via the environment:
#   HOST=18.117.72.200 SSHUSER=ubuntu KEY=~/spectre.pem REMOTE_DIR=~/validate ./fetch.sh
#
set -eu

HOST="${HOST:-18.117.72.200}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/spectre.pem}"
REMOTE_DIR="${REMOTE_DIR:-~/validate}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUERY_DIR="$SCRIPT_DIR/queries"
DATA_DIR="$SCRIPT_DIR/data"
mkdir -p "$DATA_DIR"

SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 $SSHUSER@$HOST"

for spec in "$QUERY_DIR"/*.json; do
    name="$(basename "$spec")"
    echo "== $name"
    # The management command prints only the JSON document on stdout.
    $SSH "cd $REMOTE_DIR && sudo docker compose exec -T backend python manage.py statistics_query -" \
        < "$spec" > "$DATA_DIR/$name"
done

echo "fetched $(ls "$DATA_DIR"/*.json | wc -l) result(s) into $DATA_DIR"
