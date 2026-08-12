#!/bin/bash
# Harvests "Peak RSS for" lines from the validate_worker service logs into a
# persistent, deduplicated file -- container logs are lost on redeploy, this
# file is not. Cron: every 10 min. Override OUT via env prefix in the cron
# line (PROD: OUT=/data/srv/perf-collected/peak_rss.log).
OUT=${OUT:-/home/geert/runbooks/observability/perf-metrics/collected/peak_rss.log}
mkdir -p "$(dirname "$OUT")"
TMP=$(mktemp)
timeout 100 docker service logs validate_worker --since 30m 2>&1 | grep "Peak RSS for" >> "$OUT" 2>/dev/null
sort -u "$OUT" > "$TMP" && mv "$TMP" "$OUT"
