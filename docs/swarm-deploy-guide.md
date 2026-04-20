# Swarm Deploy Guide

Copy-paste commands for deploying and operating the Validation Service on Docker Swarm.

For architecture decisions, known issues, env file strategy, and gotchas, see [swarm-considerations.md](swarm-considerations.md).

---

## Deploy

```bash
# Build, push images to registry, and deploy
make swarm-push ENV_FILE=<env_file>
make start-swarm-nodb ENV_FILE=<env_file>    # external DB (Azure DEV/PROD)
# or: make start-swarm ENV_FILE=<env_file>   # containerized DB (Hetzner)
# or: make start-swarm-local ENV_FILE=<env_file>  # local testing (no NFS, no ClamAV)

# Verify — all services should reach 1/1 within ~60s
watch docker service ls
```

## Redeploy (after code changes)

No rolling updates with `latest` tags — must tear down and redeploy.

```bash
make stop-swarm
# Wait ~15s for network cleanup
make swarm-push ENV_FILE=<env_file>
make start-swarm-nodb ENV_FILE=<env_file>
watch docker service ls
```

To force-restart a single service (same image, same env):
```bash
docker service update --force validate_backend
```

## Add / Remove Worker Nodes

### Prerequisites

1. Worker VM must be in the same VNet/subnet as the manager
2. Manager's SSH key must be on the worker (`~/.ssh/authorized_keys`). On Azure, use Portal > "Reset password > Add SSH public key"
3. Register the worker in the env file:
   ```
   SWARM_WORKER_1=dev-vm-worker-1:10.0.0.4
   ```

### Add

```bash
# Installs Docker, configures registry, joins Swarm — all in one command
make add-worker NAME=dev-vm-worker-1 ENV_FILE=.env.DEV_SWARM
```

### Remove

```bash
# Drains tasks, leaves Swarm, removes node
make remove-worker NAME=dev-vm-worker-1 ENV_FILE=.env.DEV_SWARM

# Then: remove SWARM_WORKER_N line from env file, delete VM if temporary
```

## Scale Workers

```bash
# Scale to N worker containers (distributed across nodes)
make scale-workers WORKERS=4

# Check which node each worker runs on
docker service ps validate_worker

# Set resource limits per container
make set-worker-limits CPU=2 MEM=2G CPU_RES=1 MEM_RES=1G
```

**Terminology:** A worker _node_ is a VM. Each node runs worker _replicas_ (containers). Each replica runs multiple Celery _processes_ (set by `CELERY_CONCURRENCY`, default 4).

## Monitoring

```bash
make swarm-status                            # service overview + worker placement
docker service logs -f validate_worker       # follow logs (also: backend, frontend, scheduler)
docker stats --no-stream                     # CPU/memory per container
docker node ls                               # node health
journalctl -k | grep "out of memory"         # check for OOM kills
```

## Stop / Start

```bash
make stop-swarm          # removes stack, keeps volumes and Swarm membership
make start-swarm-nodb ENV_FILE=<env_file>    # redeploy — volumes are still there
```

## Full Reset

Removes everything — stack, volumes, images, Swarm. Start fresh from first-time setup.

```bash
make stop-swarm
docker rm -f registry
docker volume prune -f          # WARNING: deletes DB data and uploaded files
docker system prune -af
docker swarm leave --force
```

---

## First-Time Setup (Manager Node)

One-time setup for a new manager. Once done, use the commands above for daily operations.

```bash
# 1. Init Swarm
docker swarm init --advertise-addr <PRIVATE_IP>

# 2. Start local registry
docker run -d --name registry -p 5000:5000 --restart always registry:2

# 3. Configure insecure registry (required for multi-node)
#    Add "insecure-registries": ["<PRIVATE_IP>:5000"] to /etc/docker/daemon.json
#    Then: sudo systemctl restart docker

# 4. Set up NFS
apt install -y nfs-kernel-server
mkdir -p /srv/nfs/files_data /srv/nfs/gherkin_logs
chown nobody:nogroup /srv/nfs/files_data /srv/nfs/gherkin_logs
chmod 777 /srv/nfs/files_data /srv/nfs/gherkin_logs

cat >> /etc/exports << 'EOF'
/srv/nfs/files_data  10.0.0.0/16(rw,sync,no_subtree_check,no_root_squash)
/srv/nfs/gherkin_logs 10.0.0.0/16(rw,sync,no_subtree_check,no_root_squash)
EOF

exportfs -ra && systemctl restart nfs-kernel-server

# 5. Create .VERSION
echo "1.0.0" > .VERSION

# 6. Prepare env file — see swarm-considerations.md for env file strategy
cp .env .env.myserver   # customize: PUBLIC_URL, DJANGO_ALLOWED_HOSTS, NFS_SERVER_IP, REGISTRY, etc.

# 7. Fetch submodules, build, deploy
make fetch-modules
make swarm-push ENV_FILE=<env_file>
make start-swarm-nodb ENV_FILE=<env_file>
```

### Migrating from Docker Compose

```bash
# Stop old stack
docker compose -f docker-compose.load_balanced.nodb.yml --env-file .env.DEV down

# Copy data from compose volumes to NFS (volume names differ: validation-service_* vs validate_*)
docker run --rm -v validation-service_files_data:/src -v /srv/nfs/files_data:/dst alpine sh -c "cp -a /src/. /dst/"
docker run --rm -v validation-service_gherkin_rules_log_data:/src -v /srv/nfs/gherkin_logs:/dst alpine sh -c "cp -a /src/. /dst/"

# Copy SSL certs (after first deploy)
cp -a docker/frontend/letsencrypt/* /var/lib/docker/volumes/validate_letsencrypt_data/_data/
docker service update --force validate_frontend
```

---

## Quick Reference

| Task | Command |
|---|---|
| Deploy (external DB) | `make start-swarm-nodb ENV_FILE=<env_file>` |
| Deploy (with DB) | `make start-swarm ENV_FILE=<env_file>` |
| Stop | `make stop-swarm` |
| Build + push | `make swarm-push ENV_FILE=<env_file>` |
| Scale workers | `make scale-workers WORKERS=4` |
| Set limits | `make set-worker-limits CPU=2 MEM=2G` |
| Add worker | `make add-worker NAME=<name> ENV_FILE=<env_file>` |
| Remove worker | `make remove-worker NAME=<name> ENV_FILE=<env_file>` |
| Status | `make swarm-status` |
| Logs | `docker service logs -f validate_<service>` |
| Force-restart | `docker service update --force validate_<service>` |
