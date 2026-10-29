#!/bin/sh
# Writes Docker Swarm control-plane state as Prometheus textfile metrics:
# per service desired vs running replicas, per node its readiness.
#
# Why: Swarm silently self-heals (restarts, rollbacks). A rolled-back service
# looks "Running" everywhere while the wrong image serves traffic, and an
# OOM-killed subprocess leaves no failed container behind. These gauges make
# "what should run" vs "what actually runs" visible.
#
# Install as a cron on the MANAGER, e.g.:  */2 * * * * <path>/swarm-state-textfile.sh <TEXTFILE_DIR>
# The output dir must be the one served by the textfile_exporter service.
set -u
OUT_DIR="${1:?usage: $0 <textfile-dir>}"
OUT="$OUT_DIR/swarm_state.prom"
TMP="$OUT.$$.tmp"

{
  echo "# HELP swarm_service_replicas_desired Replicas the service is configured to run."
  echo "# TYPE swarm_service_replicas_desired gauge"
  echo "# HELP swarm_service_replicas_running Replicas actually running right now."
  echo "# TYPE swarm_service_replicas_running gauge"
  docker service ls --format '{{.Name}} {{.Replicas}}' | while read -r name replicas _; do
    running=${replicas%%/*}
    desired=${replicas##*/}; desired=${desired%% *}
    echo "swarm_service_replicas_desired{service=\"$name\"} $desired"
    echo "swarm_service_replicas_running{service=\"$name\"} $running"
  done

  echo "# HELP swarm_node_ready 1 when the node reports status Ready, else 0."
  echo "# TYPE swarm_node_ready gauge"
  docker node ls --format '{{.Hostname}} {{.Status}}' | while read -r host status _; do
    ready=0; [ "$status" = "Ready" ] && ready=1
    echo "swarm_node_ready{node=\"$host\"} $ready"
  done
} > "$TMP"

mv "$TMP" "$OUT"   # atomic: the exporter never sees a half-written file
chmod 644 "$OUT"
