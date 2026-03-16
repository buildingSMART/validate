# Swarm Operations Runbook

Copy-paste-ready commands for every Swarm operation. Refer to [swarm-considerations.md](swarm-considerations.md) for architecture, known issues, and design decisions.

Last updated: 2026-03-16

---

## Table of Contents

1. [First-Time Setup (Manager Node)](#1-first-time-setup-manager-node)
2. [Build, Push and Deploy](#2-build-push-and-deploy)
3. [Set Up NFS (Multi-Node)](#3-set-up-nfs-multi-node)
4. [Add a Worker Node to the Swarm](#4-add-a-worker-node-to-the-swarm)
5. [Scale Workers](#5-scale-workers)
6. [Redeploy After Code Changes](#6-redeploy-after-code-changes)
7. [Monitoring and Logs](#7-monitoring-and-logs)
8. [Shut Down the Swarm](#8-shut-down-the-swarm)
9. [Remove a Worker Node](#9-remove-a-worker-node)
10. [Full Reset (Nuclear Option)](#10-full-reset-nuclear-option)
11. [Environment File Strategy](#11-environment-file-strategy)
12. [Quick Reference Card](#12-quick-reference-card)

---

## 1. First-Time Setup (Manager Node)

Run once per machine that will act as a Swarm manager. This covers everything: Swarm init, NFS, registry, env, build, deploy.

```bash
# 1a. Initialize Swarm
docker swarm init --advertise-addr <PRIVATE_IP>

# 1b. Create .VERSION (gitignored, required by make build)
echo "1.0.0" > .VERSION

# 1c. Prepare the .env file
# Copy .env (committed defaults) and customize for this server:
cp .env .env.myserver   # name it after the environment: .env.hetzner, .env.DEV_SWARM, .env.PROD
# Edit manually — no spaces around '='. Variables you MUST change:
#   PUBLIC_URL              — server URL (e.g. http://10.0.0.3 or https://validate.example.org)
#   DJANGO_ALLOWED_HOSTS    — space-separated hostnames/IPs that Django accepts
#   DJANGO_TRUSTED_ORIGINS  — space-separated origins for CSRF
#   DJANGO_SECRET_KEY       — generate a random key for non-dev environments
#   POSTGRES_PASSWORD       — use a strong password for non-dev environments
# Variables to ADD (not in the base .env, Swarm-only):
#   NFS_SERVER_IP           — private IP of the NFS server (e.g. 10.0.0.3)
#   REGISTRY                — Docker registry address (e.g. localhost:5000)
# Optional (uncomment to set):
#   CERTBOT_DOMAIN          — real domain for SSL (leave as _ to skip)
#   CERTBOT_EMAIL           — email for Let's Encrypt
#   WORKER_CPU_LIMIT, WORKER_MEMORY_LIMIT, etc. — resource limits

# 1d. Start local registry (as plain container, NOT Swarm service)
docker run -d --name registry -p 5000:5000 --restart always registry:2
# Verify:
curl -s http://localhost:5000/v2/   # should return {}

# 1e. Set up NFS on the host
apt install -y nfs-kernel-server
mkdir -p /srv/nfs/files_data /srv/nfs/gherkin_logs
chown nobody:nogroup /srv/nfs/files_data /srv/nfs/gherkin_logs
chmod 777 /srv/nfs/files_data /srv/nfs/gherkin_logs

cat >> /etc/exports << 'EOF'
/srv/nfs/files_data  10.0.0.0/16(rw,sync,no_subtree_check,no_root_squash)
/srv/nfs/gherkin_logs 10.0.0.0/16(rw,sync,no_subtree_check,no_root_squash)
EOF

exportfs -ra
systemctl restart nfs-kernel-server
showmount -e localhost

# 1f. (If migrating from docker-compose) Stop the old stack first
docker compose -f docker-compose.load_balanced.nodb.yml --env-file .env.DEV down
# Volume names differ: compose uses "validation-service_files_data", swarm uses "validate_files_data"
# Check which volumes have data:
docker system df -v | grep -A 50 "Local Volumes"

# 1g. Copy existing data from Docker volumes to NFS
# Use the COMPOSE volume name (validation-service_*), not the swarm name (validate_*):
docker run --rm -v validation-service_files_data:/src -v /srv/nfs/files_data:/dst alpine sh -c "cp -a /src/. /dst/"
docker run --rm -v validation-service_gherkin_rules_log_data:/src -v /srv/nfs/gherkin_logs:/dst alpine sh -c "cp -a /src/. /dst/"
# Verify:
du -sh /srv/nfs/files_data /srv/nfs/gherkin_logs

# 1h. (If migrating) Copy SSL certs to Swarm volume
# Old compose used a bind mount (docker/frontend/letsencrypt/), Swarm uses a named volume.
# Deploy first (step 1j), then copy certs into the volume and restart frontend:
# cp -a docker/frontend/letsencrypt/* /var/lib/docker/volumes/validate_letsencrypt_data/_data/
# docker service update --force validate_frontend

# 1i. Fetch submodules
make fetch-modules

# 1j. Build, push, deploy
make swarm-push
# For external DB (Azure):  make start-swarm-nodb ENV_FILE=.env.DEV_SWARM
# For containerized DB:     make start-swarm ENV_FILE=.env.hetzner
make start-swarm-nodb ENV_FILE=.env.DEV_SWARM

# 1k. Verify
watch docker service ls
```

Adjust NFS exports CIDR to match the network (Azure VNet: `10.0.0.0/16`, Hetzner: `10.0.0.0/24` or `*`).

See [swarm-considerations.md](swarm-considerations.md) for known issues and gotchas that can trip you up during setup (NFS volume caching, network race conditions, env file format, registry config, SSL cert migration, etc.).

---

## 2. Build, Push and Deploy

```bash
# Build, tag and push to registry (swarm-push includes build)
make swarm-push ENV_FILE=<your-env-file>

# Deploy — pick the right target:
# Full stack with DB container + NFS:
make start-swarm ENV_FILE=<your-env-file>

# External DB (e.g. Azure PostgreSQL) + NFS:
make start-swarm-nodb ENV_FILE=<your-env-file>

# Single-node / local testing (no NFS, no ClamAV, 1 replica each):
make start-swarm-local ENV_FILE=<your-env-file>

# 2b. Watch services come up (all should reach 1/1 within ~60s)
watch docker service ls

# Verify endpoints
curl -s -o /dev/null -w "%{http_code}" http://localhost/         # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/      # 302
curl -s -o /dev/null -w "%{http_code}" http://localhost/admin/    # 302

# 2c. (Optional) Set resource limits on workers
make set-worker-limits CPU=2 MEM=2G                        # limits only
make set-worker-limits CPU=2 MEM=2G CPU_RES=1 MEM_RES=1G   # limits + reservations
```

**What `start-swarm` vs `start-swarm-nodb` vs `start-swarm-local` does:**

| | `start-swarm` | `start-swarm-nodb` | `start-swarm-local` |
|---|---|---|---|
| Compose file | `swarm.yml` | `swarm.nodb.yml` | `swarm.yml` + `swarm.local.yml` |
| Database | Containerized PostgreSQL | External (e.g. Azure) | Containerized PostgreSQL |
| Volumes | NFS | NFS | Plain local volumes |
| ClamAV | Runs | Runs | Skipped |
| Replicas | backend: 2, worker: 2 | backend: 2, worker: 2 | All 1 |
| Use case | Hetzner, self-hosted | DEV/PROD (Azure DB) | Quick local testing |

---

## 3. Set Up NFS (Multi-Node)

Required before adding worker nodes. Workers need shared access to uploaded IFC files and gherkin logs.

### 3a. On the NFS server (typically the manager node)

```bash
# Install NFS
apt install -y nfs-kernel-server

# Create export directories
mkdir -p /srv/nfs/files_data /srv/nfs/gherkin_logs
chown nobody:nogroup /srv/nfs/files_data /srv/nfs/gherkin_logs
chmod 777 /srv/nfs/files_data /srv/nfs/gherkin_logs

# Configure exports
cat >> /etc/exports << 'EOF'
/srv/nfs/files_data  10.0.0.0/16(rw,sync,no_subtree_check,no_root_squash)
/srv/nfs/gherkin_logs 10.0.0.0/16(rw,sync,no_subtree_check,no_root_squash)
EOF

exportfs -ra
systemctl restart nfs-kernel-server

# Verify
showmount -e localhost
```

### 3b. Copy existing data to NFS (if migrating from local volumes)

```bash
# Copy files_data
docker run --rm \
  -v validate_files_data:/src \
  -v /srv/nfs/files_data:/dst \
  alpine sh -c "cp -a /src/. /dst/"

# Copy gherkin_logs
docker run --rm \
  -v validate_gherkin_rules_log_data:/src \
  -v /srv/nfs/gherkin_logs:/dst \
  alpine sh -c "cp -a /src/. /dst/"

# Verify
ls -la /srv/nfs/files_data/
ls -la /srv/nfs/gherkin_logs/
```

**Note:** If migrating from Docker Compose, the volume names may be prefixed differently (e.g. `validation-service_files_data` instead of `validate_files_data`). Check with `docker volume ls`.

### 3c. Set NFS_SERVER_IP in the env file

```bash
# In your env file (.env.hetzner, .env.DEV_SWARM, .env.PROD, etc.):
NFS_SERVER_IP=<private IP of the NFS server>
# e.g. on Hetzner test server this was 10.0.0.3 — check your actual network with: hostname -I
```

The `docker-compose.swarm.yml` uses this in the NFS volume driver options.

### 3d. Redeploy with NFS volumes

```bash
# Tear down existing stack (uses local volumes)
make stop-swarm

# Wait ~15 seconds for cleanup, then redeploy with NFS
make start-swarm ENV_FILE=<your-env-file>

# Verify NFS volumes are mounted
docker volume inspect validate_files_data
# Should show Type: nfs in Options
```

---

## 4. Add a Worker Node to the Swarm

### 4a. On the manager — get join token

```bash
docker swarm join-token worker
# Outputs: docker swarm join --token SWMTKN-... <manager-ip>:2377
```

### 4b. On the new worker node — prerequisites

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Install NFS client (needed for NFS volumes)
apt install -y nfs-common

# Verify NFS is reachable
mount -t nfs4 <NFS_SERVER_IP>:/srv/nfs/files_data /mnt && ls /mnt && umount /mnt

# Configure insecure registry (if using private registry over HTTP)
echo '{ "insecure-registries": ["<MANAGER_PRIVATE_IP>:5000"] }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

### 4c. Join the swarm

```bash
# Paste the join command from step 4a:
docker swarm join --token SWMTKN-... <manager-ip>:2377
```

### 4d. Verify on manager

```bash
docker node ls
# Should show both nodes as Ready/Active
```

### 4e. Also configure insecure registry on manager (if using private IP for registry)

```bash
# Only needed if REGISTRY=<MANAGER_PRIVATE_IP>:5000 instead of localhost:5000
echo '{ "insecure-registries": ["<MANAGER_PRIVATE_IP>:5000"] }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

**Important:** When using a private IP registry (e.g. `REGISTRY=10.0.0.3:5000`), EVERY node (manager AND workers) needs the insecure registry configured in `/etc/docker/daemon.json`. Otherwise workers get `No such image` errors.

---

## 5. Scale Workers

```bash
# Scale to N workers (Swarm distributes across available nodes)
make scale-workers WORKERS=4

# Check placement — see which node each worker is on
docker service ps validate_worker

# Set resource limits (applied per-container, not total)
make set-worker-limits CPU=2 MEM=2G                        # limits only
make set-worker-limits CPU=2 MEM=2G CPU_RES=1 MEM_RES=1G   # limits + reservations
```

**Per-environment resource limits:**

| Environment | CPU limit | Memory limit | Notes |
|---|---|---|---|
| Hetzner (8GB, no ClamAV) | 2 | 2G | Max ~2 workers |
| DEV | 1 | 1G | |
| PROD | 4 | 4G | Includes ClamAV ~1GB |

**ClamAV RAM warning:** Each worker with ClamAV loads ~1GB of virus signatures. 4 workers + 1 scheduler = ~5GB just for ClamAV. Use the local override (skips ClamAV) on small servers, or use 16GB+ RAM.

---

## 6. Redeploy After Code Changes

There is no rolling update for `latest` tags — must tear down and redeploy.

```bash
# 1. Stop
make stop-swarm

# 2. Rebuild and push
make swarm-push ENV_FILE=<your-env-file>

# 3. Redeploy
make start-swarm ENV_FILE=<your-env-file>

# 4. Verify
watch docker service ls
```

**Faster alternative for single-service changes:**

```bash
# Force-restart one service (uses existing image, same config — does NOT re-read .env)
docker service update --force validate_backend

# Or rebuild and push just the backend image, then update (still same env):
make swarm-push ENV_FILE=<your-env-file>
docker service update --image localhost:5000/validationsvc-backend:latest --force validate_backend

# To pick up .env changes, you must redeploy (stop + start-swarm)
```

---

## 7. Monitoring and Logs

```bash
# Service overview
docker service ls

# Detailed worker status (shows which node, current state)
make swarm-status

# Follow logs for a service
docker service logs -f validate_frontend
docker service logs -f validate_backend
docker service logs -f validate_worker
docker service logs -f validate_scheduler
docker service logs -f validate_db

# Resource usage (CPU/memory per container)
docker stats --no-stream

# Check for OOM kills
journalctl -k | grep "out of memory"

# Check node status
docker node ls

# Inspect a specific service
docker service inspect validate_worker --pretty
```

---

## 8. Shut Down the Swarm

### Stop the stack (keeps volumes and swarm membership)

```bash
make stop-swarm
# Equivalent to: docker stack rm validate
# Volumes are preserved — data survives restarts
```

### Restart after shutdown

```bash
# Just redeploy — volumes are still there
make start-swarm ENV_FILE=<your-env-file>
```

---

## 9. Remove a Worker Node

```bash
# On manager: drain the node first (moves tasks to other nodes)
docker node update --availability drain <NODE_ID>

# Wait for tasks to migrate, then on the worker node:
docker swarm leave

# On manager: remove the node from the list
docker node rm <NODE_ID>
```

---

## 10. Full Reset (Nuclear Option)

Removes everything — stack, volumes, images, swarm.

```bash
# 1. Remove the stack
make stop-swarm

# 2. Remove registry
docker rm -f registry

# 3. Remove all volumes (WARNING: deletes DB data and uploaded files!)
docker volume prune -f

# 4. Remove all images
docker system prune -af

# 5. Leave the swarm
docker swarm leave --force

# Then start fresh from section 1
```

---

## 11. Environment File Strategy

The `.env` in the repo root is committed with safe defaults (localhost, no secrets). Each environment gets its own gitignored override.

| File | Purpose | Committed? |
|---|---|---|
| `.env` | Shared defaults for docker compose (local dev, forking) | Yes |
| `.env.hetzner` | Hetzner test server (IPs, NFS, registry) | No |
| `.env.DEV` | DEV environment (docker compose, used by CI/CD) | No |
| `.env.DEV_SWARM` | DEV Swarm deployment (external Azure DB, NFS) | No |
| `.env.PROD` | Production (real secrets, domains, SSL) | No |

**Deploy with:**
```bash
make start-swarm ENV_FILE=.env.hetzner          # Hetzner (with DB container)
make start-swarm-nodb ENV_FILE=.env.DEV_SWARM   # DEV (external Azure DB)
make start-swarm ENV_FILE=.env.PROD             # PROD
```

**What changes per environment:**

| Variable | Hetzner (test) | DEV | PROD |
|---|---|---|---|
| `DEBUG` | `True` | `True` | `False` |
| `ENV` | `Development` | `Development` | `Production` |
| `PUBLIC_URL` | `http://<server-ip>` | `https://dev.validate...` | `https://validate.buildingsmart.org` |
| `DJANGO_ALLOWED_HOSTS` | `localhost <server-ip>` | `dev.validate...` | `validate.buildingsmart.org` |
| `CERTBOT_DOMAIN` | `_` (skip SSL) | domain | domain |
| `NFS_SERVER_IP` | `10.0.0.3` | `10.0.0.5` | per-setup |
| `REGISTRY` | `localhost:5000` | `localhost:5000` | per-setup |
| `POSTGRES_PASSWORD` | `postgres` | strong | strong |
| `DJANGO_SECRET_KEY` | insecure default | random | random |
| B2C / Mailgun | empty | real creds | real creds |

**Env file format rules (Swarm env files only — `.env.hetzner`, `.env.DEV_SWARM`, etc.):**
- No spaces around `=` — the Makefile uses `grep '^VAR=' | cut -d= -f2-`
- No quotes around values — Docker passes them literally
- No angle bracket placeholders like `<VALUE>` — they get passed as literal strings

---

## 12. Quick Reference Card

| Task | Command |
|---|---|
| Deploy (local/test) | `make start-swarm-local ENV_FILE=<your-env-file>` |
| Deploy (with DB + NFS) | `make start-swarm ENV_FILE=<your-env-file>` |
| Deploy (external DB + NFS) | `make start-swarm-nodb ENV_FILE=<your-env-file>` |
| Copy SSL certs to Swarm | `cp -a docker/frontend/letsencrypt/* /var/lib/docker/volumes/validate_letsencrypt_data/_data/` |
| Restart frontend (after cert copy) | `docker service update --force validate_frontend` |
| Stop stack | `make stop-swarm` |
| Scale workers | `make scale-workers WORKERS=4` |
| Set worker limits | `make set-worker-limits CPU=2 MEM=2G` |
| Build + push images | `make swarm-push ENV_FILE=<your-env-file>` |
| Service status | `make swarm-status` |
| Follow logs | `docker service logs -f validate_<service>` |
| Force-restart service | `docker service update --force validate_backend` |
| Add worker node | `docker swarm join --token SWMTKN-... <ip>:2377` |
| Drain node | `docker node update --availability drain <id>` |
| Remove node | `docker swarm leave` (on worker) + `docker node rm <id>` (on manager) |
| Check MTU | `ping -M do -s 1372 <other-node-ip>` |

