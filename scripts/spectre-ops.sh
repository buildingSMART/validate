#!/usr/bin/env bash
#
# spectre-ops.sh - operations helper for the temporary validation deployment.
#
# Everything is driven from WSL (that is where ~/spectre.pem lives) and talks to
# the remote host over SSH. Override any of the defaults via environment:
#
#   HOST=3.15.221.40 SSHUSER=ubuntu KEY=~/spectre.pem
#
# Usage:
#   ./spectre-ops.sh survey                 # host/containers/ports overview
#   ./spectre-ops.sh status                 # pipeline progress snapshot
#   ./spectre-ops.sh monitor                # start durable 30s background sampler
#   ./spectre-ops.sh logs                   # tail worker log
#   ./spectre-ops.sh token <name>           # create user + print DRF token
#   ./spectre-ops.sh tokens <n>             # create n bulk users + print tokens
#   ./spectre-ops.sh enable-cleanup         # apply override + IMMEDIATE_STATS_AND_CLEANUP
#   ./spectre-ops.sh submit <token> [args]  # git pull ~/validate, then run ~/validate/scripts/bulk_submit.py
#   ./spectre-ops.sh batch <token> [n] [prev-state]   # seed resume state, submit n, baseline
#   ./spectre-ops.sh drain [iters]          # wait for the pipeline to drain
#   ./spectre-ops.sh rebuild                # git pull + rebuild backend image + recreate
#   ./spectre-ops.sh measure [minutes]      # timed completion/purge rate
#   ./spectre-ops.sh diag                   # task matrix, stalls, resource use, log tail
#
set -eu

HOST="${HOST:-18.119.213.101}"
SSHUSER="${SSHUSER:-ubuntu}"
KEY="${KEY:-$HOME/spectre.pem}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes $SSHUSER@$HOST"

cmd="${1:-}"
shift || true

case "$cmd" in

survey)
    $SSH 'bash -s' <<'ENDSSH'
echo "=== host ==="; hostname; uname -r; nproc; free -h | head -2
echo; echo "=== disk ==="; df -h / | tail -1
echo; echo "=== containers ==="
sudo docker ps -a --format '{{.Names}} | {{.Status}} | {{.Ports}}'
echo; echo "=== corpus ==="; ls -l ~/files.tar.gz
echo; echo "=== ports ==="; ss -ltn | grep -E ':(22|80|443|8000)\b'
ENDSSH
    ;;

status)
    $SSH 'bash -s' <<'ENDSSH'
echo "=== requests / tasks ==="
sudo docker exec -w /app/backend backend python3 manage.py shell -c "
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask
from django.utils import timezone
from datetime import timedelta
import collections
q = ValidationRequest.objects
print('requests :', dict(collections.Counter(q.values_list('status', flat=True))))
print('purged   :', q.filter(file_removed__isnull=False).count(), '/', q.count())
print('tasks    :', dict(collections.Counter(ValidationTask.objects.values_list('status', flat=True))))
cut = timezone.now() - timedelta(minutes=10)
print('tasks ended last 10min:', ValidationTask.objects.filter(ended__gte=cut).count())
" 2>&1 | grep -v 'objects imported'
echo
echo -n "celery queue   : "; sudo docker exec redis redis-cli LLEN celery
echo -n "antivirus queue: "; sudo docker exec redis redis-cli LLEN antivirus
echo
echo -n "tarball intact : "; ls -l ~/files.tar.gz | awk '{print $5" bytes"}'
if pgrep -f 'tar tvzf' > /dev/null; then
    echo "listing        : RUNNING ($(wc -l < ~/members.tsv) members so far)"
else
    echo "listing        : FINISHED ($(wc -l < ~/members.tsv) members)"
fi
ENDSSH
    ;;

monitor)
    $SSH 'bash -s' <<'ENDSSH'
pkill -f 'bulk_monitor.sh' 2>/dev/null || true
cat > /home/ubuntu/bulk_monitor.sh <<'EOS'
#!/bin/bash
LOG=/home/ubuntu/monitor.log
while true; do
  q=$(docker exec redis redis-cli LLEN celery 2>/dev/null | tr -d '\r'); q=${q:-0}
  stats=$(docker exec -w /app/backend backend python3 manage.py shell -c "
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask
q = ValidationRequest.objects
print(q.count(),
      q.filter(status='PENDING').count(),
      q.filter(status='INITIATED').count(),
      q.filter(status='COMPLETED').count(),
      q.filter(status='FAILED').count(),
      q.filter(file_removed__isnull=False).count(),
      ValidationTask.objects.filter(status='FAILED').count())
" 2>/dev/null | tail -1)
  [ -z "$stats" ] && stats="? ? ? ? ? ? ?"
  echo "$(date +%H:%M:%S) celery=$q (tot pend init done fail purged taskfail)=$stats" >> "$LOG"
  sleep 30
done
EOS
chmod +x /home/ubuntu/bulk_monitor.sh
setsid nohup sudo /home/ubuntu/bulk_monitor.sh > /dev/null 2>&1 < /dev/null &
sleep 2
echo "monitor started; tail it with:  tail -f /home/ubuntu/monitor.log"
ENDSSH
    ;;

logs)
    $SSH "sudo docker logs --tail ${1:-60} -f worker 2>&1"
    ;;

token)
    name="${1:?usage: token <name>}"
    $SSH "sudo docker exec -w /app/backend backend python3 manage.py shell -c \"
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
U = get_user_model()
u, created = U.objects.get_or_create(username='${name}')
u.is_active = True; u.email = '${name}@localhost'; u.set_password('${name}'); u.save()
t, _ = Token.objects.get_or_create(user=u)
print('user=${name}', 'created' if created else 'existing', 'token=' + t.key)
\"" 2>&1 | grep -v 'objects imported'
    ;;

tokens)
    n="${1:?usage: tokens <n>}"
    for i in $(seq 1 "$n"); do
        "$0" token "bulk$i"
    done
    ;;

enable-cleanup)
    scp -i "$KEY" -o StrictHostKeyChecking=no \
        "$SCRIPT_DIR/docker-compose.override.yml" "$SSHUSER@$HOST:~/validate/docker-compose.override.yml" >/dev/null
    $SSH 'bash -s' <<'ENDSSH'
set -eu
cd ~/validate
if grep -q '^IMMEDIATE_STATS_AND_CLEANUP' .env; then
    echo "IMMEDIATE_STATS_AND_CLEANUP already in .env"
else
    printf '\n# purge each uploaded file once its validation completes\nIMMEDIATE_STATS_AND_CLEANUP = True\n' >> .env
fi
sudo docker compose config > /dev/null
echo "compose config OK"
sudo docker compose up -d 2>&1 | tail -8
sleep 25
echo -n "worker IMMEDIATE_STATS_AND_CLEANUP="
sudo docker exec worker sh -c 'echo $IMMEDIATE_STATS_AND_CLEANUP'
echo -n "clamd in worker: "
sudo docker exec worker sh -c 'pgrep -a clamd || echo NOT_RUNNING'
ENDSSH
    ;;

submit)
    token="${1:?usage: submit <token[,token2,...]> [extra args]}"
    shift || true
    limit_args="$*"
    $SSH "bash -s" <<ENDSSH
set -eu
cd ~/validate
git pull --ff-only
cd scripts
./bulk_submit.py --token '${token}' ${limit_args}
ENDSSH
    ;;

drain)
    $SSH "bash -s ${1:-120}" <<'ENDSSH'
max="$1"
i=0
while [ "$i" -lt "$max" ]; do
  i=$((i+1))
  q=$(sudo docker exec redis redis-cli LLEN celery 2>/dev/null | tr -d '\r'); q=${q:-0}
  stats=$(sudo docker exec -w /app/backend backend python3 manage.py shell -c "
from apps.ifc_validation_models.models import ValidationRequest
q = ValidationRequest.objects
print(q.filter(status='PENDING').count(),
      q.filter(status='INITIATED').count(),
      q.filter(status='COMPLETED').count(),
      q.filter(status='FAILED').count(),
      q.filter(file_removed__isnull=False).count())
" 2>/dev/null | tail -1)
  [ -z "$stats" ] && stats="9 9 9 9 9"
  echo "[$(date +%H:%M:%S)] celery=$q (pending init done fail purged)=$stats"
  set -- $stats
  if [ "$q" = "0" ] && [ "${1:-1}" = "0" ] && [ "${2:-1}" = "0" ]; then
    echo DRAINED; break
  fi
  sleep 30
done
ENDSSH
    ;;

rebuild)
    $SSH 'bash -s' <<'ENDSSH'
set -u
cd ~/validate
echo "=== git pull ==="
git pull --ff-only 2>&1 | tail -8
VERSION="$(cat .VERSION 2>/dev/null || echo dev)"
HASH="$(git rev-parse --short HEAD)"
echo "=== building backend image ($HASH) ==="
sudo docker compose build --build-arg GIT_COMMIT_HASH="$HASH" \
    --build-arg VERSION="$VERSION" backend 2>&1 | tail -5
echo "=== recreating ==="
sudo docker compose up -d 2>&1 | tail -6
sleep 40
echo "=== verify ==="
echo -n "  IMMEDIATE_STATS_AND_CLEANUP="
sudo docker exec worker sh -c 'echo $IMMEDIATE_STATS_AND_CLEANUP'
echo -n "  clamd: "
sudo docker exec worker sh -c 'pgrep -a clamd || echo NOT_RUNNING'
sudo docker ps --format '  {{.Names}} | {{.Status}}'
ENDSSH
    ;;

measure)
    $SSH "bash -s ${1:-20}" <<'ENDSSH'
minutes="$1"
first_done=""; first_time=""; i=0
while [ "$i" -lt "$minutes" ]; do
  i=$((i+1))
  q=$(sudo docker exec redis redis-cli LLEN celery 2>/dev/null | tr -d '\r'); q=${q:-0}
  stats=$(sudo docker exec -w /app/backend backend python3 manage.py shell -c "
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask
q = ValidationRequest.objects
print(q.filter(status='COMPLETED').count(),
      q.filter(status='INITIATED').count(),
      q.filter(status='FAILED').count(),
      q.filter(file_removed__isnull=False).count(),
      ValidationTask.objects.filter(status='FAILED').count())
" 2>/dev/null | tail -1)
  [ -z "$stats" ] && stats="? ? ? ? ?"
  cpu=$(sudo docker stats --no-stream --format '{{.CPUPerc}}' worker 2>/dev/null | tr -d '\r')
  read -r done init fail purged tfail <<<"$stats"
  [ -z "$first_done" ] && [ "$done" != "?" ] && { first_done="$done"; first_time=$(date +%s); }
  echo "[$(date +%H:%M:%S)] celery=$q completed=$done initiated=$init purged=$purged failed=$fail taskfail=$tfail workerCPU=$cpu"
  [ "$q" = "0" ] && [ "$init" = "0" ] && { echo "ALL DRAINED"; break; }
  sleep 60
done
now=$(date +%s); elapsed=$(( now - first_time )); delta=$(( done - first_done ))
echo
echo "=========== THROUGHPUT ==========="
echo "window        : ${elapsed}s"
echo "completed     : $first_done -> $done"
[ "$elapsed" -gt 0 ] && echo "throughput    : ~$(echo "scale=1; $delta * 3600 / $elapsed" | bc) files/hour"
echo "still initiated: $init"
echo "failed         : $fail (tasks: $tfail)"
echo "purged files   : $purged"
ENDSSH
    ;;

diag)
    $SSH 'bash -s' <<'ENDSSH'
sudo docker exec -w /app/backend backend python3 manage.py shell -c "
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask
from django.utils import timezone
import collections
print('--- tasks by type/status ---')
m = collections.Counter(ValidationTask.objects.values_list('type','status'))
for k in sorted(m): print('  %-22s %-10s %d' % (k[0], k[1], m[k]))
print('--- requests by status ---')
print(' ', dict(collections.Counter(ValidationRequest.objects.values_list('status', flat=True))))
print('  purged:', ValidationRequest.objects.filter(file_removed__isnull=False).count())
print('--- FAILED requests (status_reason) ---')
for r in ValidationRequest.objects.filter(status='FAILED').order_by('-id')[:12]:
    print('  %-12s %-38s %s' % (r.public_id, r.file_name[:38], (r.status_reason or '')[:170]))
print('--- FAILED tasks ---')
for t in ValidationTask.objects.filter(status='FAILED')[:12]:
    print('  %-22s req=%-12s %s' % (t.type, t.request.public_id, (t.status_reason or '')[:140]))
now = timezone.now()
print('--- oldest INITIATED tasks ---')
for t in ValidationTask.objects.filter(status='INITIATED').order_by('started')[:8]:
    age = (now - t.started).total_seconds() if t.started else -1
    print('  %-22s req=%-12s age=%.0fs' % (t.type, t.request.public_id, age))
" 2>&1 | grep -v 'objects imported'
echo
free -h | head -2
sudo docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}' worker av_worker backend 2>&1
echo
echo "--- recent errors (if any) ---"
sudo docker logs --tail 400 worker 2>&1 | grep -iE 'error|traceback|retry|raised' | tail -12 | cut -c1-170
echo
echo "--- log tail ---"
sudo docker logs --tail 8 worker 2>&1 | cut -c1-170
ENDSSH
    ;;

batch)
    token="${1:?usage: batch <token[,token2,...]> [n] [prev-state-file]}"
    n="${2:-50}"
    prev="${3:-}"
    $SSH "bash -s $n '$token' '$prev'" <<'ENDSSH'
set -u
n="$1"; token="$2"; prev="$3"
cd ~

stamp=$(date +%H%M%S)
state="batch_${stamp}_state.jsonl"
log="batch_${stamp}_log.jsonl"
if [ -n "$prev" ] && [ -f "$prev" ]; then
    cp -f "$prev" "$state"
    echo "seeded resume state from $prev"
fi

echo "=== BASELINE ==="
sudo docker exec -w /app/backend backend python3 manage.py shell -c "
from apps.ifc_validation_models.models import ValidationRequest, ValidationTask
q = ValidationRequest.objects
print('  requests=%d completed=%d initiated=%d failed=%d purged=%d taskfail=%d' % (
    q.count(), q.filter(status='COMPLETED').count(), q.filter(status='INITIATED').count(),
    q.filter(status='FAILED').count(), q.filter(file_removed__isnull=False).count(),
    ValidationTask.objects.filter(status='FAILED').count()))
" 2>&1 | grep -v 'objects imported'

echo
echo "=== submitting $n (state=$state) ==="
date +%H:%M:%S
git -C ~/validate pull --ff-only
~/validate/scripts/bulk_submit.py --limit "$n" --token "$token" --state ~/"$state" --log ~/"$log" 2>&1 | tail -12
date +%H:%M:%S
echo -n "celery queue: "; sudo docker exec redis redis-cli LLEN celery
echo "STATE_FILE=$state"
ENDSSH
    ;;

*)
    sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
