# Docker Swarm — Considerations & Known Issues

Compiled during IVS-719 development. Grouped by category.

## Status

- **Single-node Swarm**: tested and working (Hetzner, 2026-03-10)
- **Multi-node Swarm**: tested and working with 2 nodes + NFS (Hetzner, 2026-03-15)
- **Single-node Swarm on Azure DEV**: tested and working with external DB + NFS (2026-03-15)
- **Multi-node Swarm on Azure DEV**: tested and working — manager + worker node, tasks distributed across both (2026-03-16)
- **CI/CD**: not yet adapted for Swarm — see section 5
- **SSL/Certbot**: not tested with a real domain yet (using `CERTBOT_DOMAIN=_` to skip)
- **Documentation**: user-facing docs (README, deployment guide) not yet updated for Swarm workflow

---

# Architecture & Design

## 1. Architecture overview

Every worker needs access to `/files_storage` (uploaded IFC files) and `/gherkin_logs`. In Docker Compose, these are local volumes on one machine. In Swarm, workers run on **different machines** — so files must be shared via NFS.

```
                   ┌─────────┐
                   │ Frontend │  (Nginx + React)
                   │  :80/443 │
                   └────┬─────┘
                        │
                   ┌────▼─────┐
                   │ Backend  │  (Django API — manager node)
                   │  :8000   │
                   └────┬─────┘
                        │ enqueues tasks
                   ┌────▼─────┐
                   │  Redis   │  (Celery broker — manager node)
                   │  :6379   │
                   └────┬─────┘
                        │ workers consume via overlay network
              ┌─────────┼──────────┐
              │         │          │
         ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐
         │Worker 1│ │Worker 2│ │Worker N│  (any node in swarm)
         └────┬───┘ └───┬────┘ └──┬─────┘
              │         │          │
              │     NFS mount      │
              └─────────┼──────────┘
                   ┌────▼─────┐
                   │/srv/nfs/ │  (NFS server on manager node)
                   │files_data│
                   └──────────┘
                        │ same machine
                   ┌────▼─────┐
                   │ Postgres │  (manager node)
                   └──────────┘

         ┌───────────┐
         │ Scheduler │  (1 replica, manager only)
         │  --beat   │  file retention: archive@90d, remove@180d
         └───────────┘
```

**How it works:**
- The **manager node** runs: frontend, backend, DB, Redis, scheduler, and the NFS server
- **Worker nodes** only run Celery workers — they mount NFS volumes automatically via the Docker volume driver
- The **overlay network** (Docker Swarm native) connects workers to Redis and Postgres across machines
- NFS gives workers read/write access to uploaded files as if they were local

**If NFS goes down, all workers stall** — `hard,timeo=600` mount options mean workers will hang (not error) until NFS recovers. This is intentional: better to wait than to silently fail.

For Azure: restrict NFS exports to VNet CIDR (e.g. `10.0.0.0/16(rw,sync,...)`), not `*`.

---

## 2. Build and deploy are now separate steps

Docker Compose: `docker compose build && docker compose up` — build and run in one flow.

Docker Swarm: worker nodes **cannot build images**. They pull from a registry.

```
Developer machine          Registry              Swarm nodes
     build ──push──>  localhost:5000  <──pull──  worker-1, worker-2
```

Workflow:
```bash
make build                          # build images locally
make swarm-push ENV_FILE=.env.xxx   # tag + push to registry
make start-swarm ENV_FILE=.env.xxx  # docker stack deploy (nodes pull from registry)
```

For Azure PROD, replace `localhost:5000` with Azure Container Registry (ACR).

---

## 3. Worker scaling and capacity

There is **no hard cap** on worker replicas. Scaling is manual:

```bash
make scale-workers WORKERS=4
```

**Capacity math per worker:**
- ~1GB RAM for ClamAV virus signature database
- ~2-3GB RAM for Celery tasks (depends on `CELERY_CONCURRENCY`)
- Total: **~3-4GB RAM per worker**
- Each worker runs `CELERY_CONCURRENCY` parallel tasks (default: 4 in .env.hetzner, 6 in .env)

| Environment | Workers | Concurrency | Parallel tasks | RAM needed (workers only) |
|---|---|---|---|---|
| Hetzner (8GB) | 2 | 4 | 8 | ~6-8GB |
| DEV | 2 | 4 | 8 | ~6-8GB |
| PROD | 4+ | 6 | 24+ | ~12-16GB |

To prevent overloading a single node, use `max_replicas_per_node` in the compose file:
```yaml
deploy:
    replicas: 4
    placement:
        max_replicas_per_node: 2
```
This forces Swarm to spread workers across at least 2 nodes. Not currently set — all replicas can land on one node if Swarm decides to.

**Resource limits** are optional but recommended in production. Apply post-deploy:
```bash
make set-worker-limits CPU=2 MEM=2G                        # limits only
make set-worker-limits CPU=2 MEM=2G CPU_RES=1 MEM_RES=1G   # limits + reservations
```

Per-environment suggestions:
| Environment | CPU limit | Memory limit | Notes |
|---|---|---|---|
| Hetzner (8GB) | 2 | 2G | Small server, max ~2 workers |
| DEV | 1 | 1G | |
| PROD | 4 | 4G | Includes ClamAV ~1GB |

---

## 4. `.env` strategy

`.env` is committed with safe defaults (localhost, no secrets). Environment-specific files are gitignored via `.env.*`:

| File | Purpose | Committed? |
|---|---|---|
| `.env` | Shared defaults for local dev / forking | Yes |
| `.env.hetzner` | Hetzner dev server (IPs, NFS, registry) | No |
| `.env.DEV` | DEV environment (docker compose, used by CI/CD) | No |
| `.env.DEV_SWARM` | DEV Swarm deployment (external Azure DB, NFS) | No |
| `.env.PROD` | Production (real secrets, domains) | No |

Deploy with:
```bash
make start-swarm ENV_FILE=.env.hetzner          # Hetzner (with DB container)
make start-swarm-nodb ENV_FILE=.env.DEV_SWARM   # DEV (external Azure DB)
```

The Makefile uses `envsubst` to substitute **only compose-level vars** (REGISTRY, NFS_SERVER_IP, CERTBOT_DOMAIN, etc.) from the env file into the YAML, then pipes the result to `docker stack deploy`. Container env vars are loaded by `docker stack deploy` via the `env_file:` directive directly.

**Why only compose-level vars?** Earlier approaches that sourced the entire env file broke on values with special characters (`#`, `(`, spaces). The current approach extracts only the vars that `envsubst` needs (REGISTRY, CERTBOT_DOMAIN, CERTBOT_EMAIL, NFS_SERVER_IP, etc.) using `grep` + `cut` in the Makefile.

**Env file format rules (Swarm env files only — `.env.hetzner`, `.env.DEV_SWARM`, etc.):**
- No spaces around `=` — the Makefile uses `grep '^VAR=' | cut -d= -f2-`
- No quotes around values — Docker passes them literally
- No angle bracket placeholders like `<VALUE>` — they get passed as literal strings

This avoids three problems with earlier approaches:
1. **Type conversion bugs** — `docker compose config` converted ports to strings and cpus to integers, which `docker stack deploy` rejected
2. **`.env` auto-load conflict** — `docker compose config` always loads `.env` from the project directory, silently overriding values from `--env-file`
3. **Special character breakage** — sourcing the whole env file with `set -a && . ./file` breaks on values containing `#` (comment), `(` (subshell), or unquoted spaces

---

## 5. Local dev and server deploy are now different configs

You maintain two separate compose files:
- `docker-compose.yml` — local development (single machine, local volumes, `container_name`)
- `docker-compose.swarm.yml` — Swarm deployment (overlay network, NFS volumes, `deploy:` section)
- `docker-compose.swarm.nodb.yml` — Swarm with external DB (no containerized Postgres)

Risk: they drift apart over time (different env vars, image versions, volume configs). Mitigation: keep changes in sync during PRs.

---

## 6. No `container_name` / `depends_on` in Swarm

Swarm manages container naming internally (e.g. `validate_worker.1.abc123`). `depends_on` is ignored — services start simultaneously.

Current impact: minimal — entrypoints use DNS service discovery (`redis`, `db`, `backend`) and `pg_isready` wait loops. No code changes needed.

---

## 7. DNS transition strategy for PROD cutover

To avoid downtime when switching from Docker Compose to Swarm in production, use a temporary subdomain:

1. Deploy Swarm stack on a new server (or same server on different ports)
2. Point a temp subdomain to it (e.g. `swarm.validate.buildingsmart.org`)
3. Run both setups in parallel — existing Compose on the main domain, Swarm on the temp domain
4. Test via API (bulk uploads, concurrent validations) against the temp domain
5. Once confident, swap DNS: point the main domain to the Swarm deployment
6. Decommission the old Compose setup

Rollback: if Swarm has issues, DNS points back to the old setup in minutes.

For DEV: same approach, or direct cutover (lower risk since it's not user-facing).

---

# Known Issues & Gotchas

## 8. Overlay network MTU must be set to 1400

MTU (Maximum Transmission Unit) is the largest packet size a network link can carry — the default is 1500 bytes. Hetzner's private network uses MTU 1450. Docker's VXLAN overlay adds ~50 bytes of encapsulation headers to every packet, so if the underlying MTU is already ≤1500, the oversized packets get silently dropped or fragmented. Without setting the overlay MTU to 1400 (leaving headroom for the VXLAN overhead), worker nodes on different machines **cannot reach services on the manager** (DB, Redis).

Symptom: workers stuck on `db:5432 - no response` despite DNS resolving correctly.

Fix is in `docker-compose.swarm.yml`:
```yaml
networks:
    validate:
        driver: overlay
        driver_opts:
            com.docker.network.driver.mtu: "1400"
```

This applies to any cloud provider with sub-1500 MTU on internal networks.

---

## 9. ClamAV runs inside every worker (~1GB RAM overhead each)

Each worker container starts its own ClamAV daemon + freshclam (virus signature updater). This is the **same as before** — not a Swarm change. But when scaling to N workers, you get N independent ClamAV instances.

Impact:
- ~1GB RAM per worker for virus signature database (observed during Hetzner testing — 5 instances caused OOM on 8GB server)
- Each worker independently downloads signature updates on boot
- The 4GB memory limit per worker (PROD) accounts for this: ~1GB ClamAV + ~2-3GB for Celery tasks
- The local override (`docker-compose.swarm.local.yml`) skips ClamAV entirely for testing on small servers

4 workers with ClamAV = ~4GB just for virus DBs.

---

## 10. Registry must use private IP, not localhost

**Always set `REGISTRY=<manager-private-ip>:5000`** (e.g. `10.0.0.5:5000`) in the env file, never `localhost:5000`.

Why: `localhost` resolves to the local machine. On the manager, that works. On worker nodes, `localhost:5000` points to nothing — workers can't pull images and stay at 0/N replicas with `No such image` errors.

**Every node** (manager AND workers) needs the insecure registry configured in `/etc/docker/daemon.json`:

```bash
echo '{ "insecure-registries": ["10.0.0.5:5000"] }' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

The `make add-worker` target handles this automatically for workers. For the **manager**, add it manually once during initial setup (merge with any existing `daemon.json` settings like log-driver).

---

## 11. DB `postmaster.pid` disappears in Swarm (containerized DB only)

PostgreSQL starts, recovers, becomes ready — then shuts itself down because its PID file vanished:

```
could not open file "postmaster.pid": No such file or directory
performing immediate shutdown because data directory lock file is invalid
```

This is a Docker Swarm volume mount timing issue. Fix: set `restart_policy.condition: any` (not `on-failure`) on the db service so Swarm keeps restarting it until it sticks. Already applied in `docker-compose.swarm.yml`.

---

## 12. Docker caches NFS volume options

When `docker stack deploy` creates an NFS volume, the driver options (including `addr=`) are cached. If the first deploy has the wrong NFS IP (e.g. the default `10.0.0.1`), **all subsequent deploys reuse that wrong IP** — even after fixing the env file.

Symptoms: containers stuck in "Created" state, never starting. No logs. NFS mount hangs because the IP doesn't exist.

Fix:
```bash
docker stack rm validate
sleep 15
docker container prune -f
docker volume rm validate_files_data validate_gherkin_rules_log_data
# If containers are stuck on hanging NFS mount:
systemctl restart docker
# Then redeploy
make start-swarm-nodb ENV_FILE=.env.DEV_SWARM
```

Verify volume has correct IP after deploy: `docker volume inspect validate_files_data`

---

## 13. File upload: `f.seek(0)` after measuring size

In `views.py`, the upload handler seeks to the end of the file to measure its size (`f.seek(0, 2)` + `f.tell()`), then must rewind (`f.seek(0)`) before `serializer.save()`. Without the rewind, Django saves a 0-byte file because the file pointer is at the end.

This may only manifest with NFS-backed storage where buffering behaviour differs from local volumes. Commit: `012776c`

---

## 14. `determine_aggregate_status()` masks silent failures

When a validation task produces zero outcomes (e.g. subprocess crashed, worker OOM, NFS hang), the status defaults to VALID (`models.py:1297` — `# assume valid if no outcomes - TODO: is this correct?`). This pre-dates Swarm but becomes more visible when workers crash/restart across nodes.

**Why we can't just return INVALID:** Marking a file as invalid has real consequences — vendors have to investigate and fix it. Returning INVALID for a crashed task would create false negatives. The actual problem is **silent failure** — a task fails completely and nobody notices because it looks like it passed.

**What should happen instead:** When zero outcomes are produced, the system should alert developers (e.g. log an error, send a notification, or set a distinct status like `ERROR` or `INCONCLUSIVE`) rather than silently defaulting to VALID. The file should be flagged for re-validation, not marked as valid or invalid.

Not blocking for Swarm, but worth a follow-up fix.

---

## 15. DB connection pooling: stale connections on overlay network

Django's `"pool": True` (psycopg3 connection pool) keeps DB connections open for reuse. The Swarm overlay network drops idle TCP connections after ~13 minutes. When the pool hands out a dead connection, Django raises:

```
OperationalError: consuming input failed: server closed the connection unexpectedly
```

**Fix** (in `backend/core/settings.py`):
- `"pool": False` — disable psycopg3's built-in connection pool. `CONN_HEALTH_CHECKS` alone is not sufficient because the pool can hand out a stale connection after the health check passes but before it reaches the query.
- `CONN_HEALTH_CHECKS = True` — Django pings the connection before using it; if dead, it reconnects transparently
- `CONN_MAX_AGE = 600` (10 min) — keeps connections open for reuse without the pool layer

`CONN_MAX_AGE` is configurable via `POSTGRES_CONN_MAX_AGE` env var. The default of 600s works for Swarm; set to `0` to close connections after each request (safest but slower).

DB logs showing the symptom (every ~13 min):
```
LOG:  could not receive data from client: Connection reset by peer
```

---

## 16. SSL certs: bind mount vs named volume

Docker Compose used a bind mount for Let's Encrypt certs: `./docker/frontend/letsencrypt:/etc/letsencrypt`. Swarm uses a named volume (`validate_letsencrypt_data`).

When migrating, certs must be manually copied into the Swarm volume:
```bash
cp -a docker/frontend/letsencrypt/* /var/lib/docker/volumes/validate_letsencrypt_data/_data/
docker service update --force validate_frontend
```

Without this, HTTPS won't work and the site is only accessible via HTTP. Certbot renewal should continue to work inside the container since `CERTBOT_DOMAIN` is set.

---

## 17. Overlay network race condition after stack rm

After `docker stack rm`, the overlay network cleanup is asynchronous. Redeploying too quickly causes `network validate_validate not found` errors.

Fix: wait ~15 seconds between `docker stack rm` and `docker stack deploy`. If a ghost network persists (`docker network ls` shows it but `docker network rm` says "not found"), restart Docker: `systemctl restart docker`.

---

## 18. No rolling updates for `latest` tags

Swarm checks if the image tag has changed before pulling. Since all images use `:latest`, Swarm sees "same tag" and skips the pull — even if the image content has changed.

**Impact:** `docker service update --force` restarts containers but uses the **cached** image. To deploy new code, you must tear down and redeploy:

```bash
make stop-swarm
make swarm-push ENV_FILE=.env.xxx
make start-swarm ENV_FILE=.env.xxx
```

Or force a pull for a single service:
```bash
docker service update --image localhost:5000/validationsvc-backend:latest --force validate_backend
```

---

## 19. `docker service update --force` does NOT re-read env vars

`docker service update --force` restarts containers with the **same config** they were deployed with. It does NOT re-read the env file. If you changed `.env.DEV_SWARM` and want the changes to take effect, you must do a full redeploy:

```bash
make stop-swarm
# wait ~15 seconds
make start-swarm ENV_FILE=.env.DEV_SWARM
```

---

## 20. VS Code port forwarding conflicts with Swarm ingress

VS Code's SSH tunnel sometimes conflicts with Swarm's ingress routing (IPv6 issues). Accessing `localhost:80` via VS Code's forwarded port may not work.

**Workaround:** Use the server's public IP directly instead of localhost.

---

# Maintenance

## 21. CI/CD not yet adapted for Swarm

The current GitHub Actions workflow (`.github/workflows/ci_cd.yml`) uses `docker compose up` for DEV and PROD deployments. It does **not** support Swarm.

What needs to change for Swarm CI/CD:
- `docker compose up` → `make start-swarm ENV_FILE=.env.XXX` (build, push to registry, stack deploy)
- The runner/deploy target needs access to the Swarm manager (SSH or self-hosted runner on the manager node)
- Worker nodes pull images from the registry automatically — no action needed per node
- `ENV_FILE` is already a GitHub Actions variable (`${{ vars.ENV_FILE }}`) — just needs to point to the right file

Options:
1. **Self-hosted runner on the manager node** — simplest, runner has direct access to Docker and the registry
2. **SSH deploy step** — GitHub-hosted runner SSHes into the manager to run make commands
3. **Separate workflow** — new workflow file for Swarm deployments, triggered manually or on specific branches

Not blocking for merge to development — Swarm can be deployed manually until CI/CD is adapted.

---

## 22. Periodic cleanup on DEV server

> **DEV-specific** — the DEV server has a small root disk (29GB). Hetzner/PROD with larger disks are less affected but should still clean up periodically.

Docker images, build cache, orphaned volumes, and uploaded IFC files accumulate fast. Without periodic cleanup, the disk fills up and deployments fail.

**What accumulates:**
- Docker build cache (~2GB per full build cycle)
- Old/unused images (previous deployments)
- Orphaned volumes from CI/CD runs (e.g. `repo-clone_*` volumes from GitHub Actions)
- Uploaded IFC files in `files_data` volume (4GB+ and growing)

**Cleanup commands:**
```bash
# Check disk usage
df -h /

# Docker overview
docker system df

# Remove unused images and build cache
docker builder prune -af
docker image prune -af

# Remove orphaned volumes (CAREFUL: only removes volumes not attached to any container)
docker volume prune -f

# List volume sizes to find large orphans
docker system df -v | grep -A 50 "Local Volumes"
```

**Recommendation:** Run `docker system prune -af` and `docker volume prune -f` after each major deployment cycle. Consider adding this to the CI/CD pipeline or a cron job. The `/mnt` disk (74GB ephemeral Azure temp disk) can be used for temporary storage but **data is lost on VM deallocation/resize**.

---

## 23. `makemigrations` runs on every backend startup

The `server-entrypoint.sh` runs `python manage.py makemigrations` and `python manage.py migrate` on every container start. This works because:
- Backend is constrained to **1 replica** on the manager node — no migration race conditions
- The generated migration files live inside the container (ephemeral) — they're not persisted

**Risk:** If model changes exist that haven't been committed as migration files, `makemigrations` will generate them at runtime inside the container. These migrations disappear when the container restarts, potentially causing inconsistency. In production, migrations should be baked into the image at build time.

**Decision:** Kept as-is for now. Backend is always 1 replica, and in practice all migrations are committed to git before deployment. But worth revisiting for PROD hardening.

---

## 24. Historical Swarm instability

> "unexplained crashes/corrupt state (5+ years ago) — hopefully they are gone now"

Modern Docker Engine (24+) should be stable. Mitigations already in place:
- `CELERY_TASK_ACKS_LATE = True` — tasks stay in queue until completed
- `CELERY_TASK_REJECT_ON_WORKER_LOST = True` — crashed tasks are re-queued
- `restart_policy: condition: any` on DB (see section 11), `on-failure` on other services
- `update_config: failure_action: rollback` — bad deploys roll back

---

# Local Dev Only

## 25. Lima-specific: virtiofs + Celery prefork = errno 35

Celery's `prefork` pool + Lima's virtiofs read-only mounts cause `EDEADLK` deadlocks. Workaround: `--pool=solo`.

**Not a production issue** — only affects local development on macOS with Lima. Docker containers on Linux use proper ext4/overlay2 filesystems.

---

## 26. macOS NFS gotcha: `/tmp` vs `/private/tmp`

On macOS, `/tmp` is a symlink to `/private/tmp`. NFS exports must use the real path (`/private/tmp/...`). Not relevant for Linux servers (Hetzner/Azure), but relevant for local development on macOS.
