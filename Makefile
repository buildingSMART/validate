none:
	@echo ERROR: Enter at least one target (start, start-load-balanced, start-full, start-infra-only, stop, build, rebuild, clean, fetch-modules)

# minimal setup (w/o observability/scaling etc...)
start:
	docker compose -f docker-compose.yml up -d

# minimal setup using an existing external database (w/o observability/scaling etc...)
start-nodb:
	docker compose -f docker-compose.nodb.yml up -d

# typical load balanced setup (multiple workers/backend)
start-load-balanced:
	docker compose -f docker-compose.load_balanced.yml up -d

# full setup (load balanced, OTel, Prometheus/Grafana, etc...)
start-full:
	docker compose -f docker-compose.full.yml up -d

# infra only (redis, postgres, flower)
start-infra: start-infra-only

start-infra-only:
	docker compose -f docker-compose.infra_only.yml up -d

stop:
	docker compose down

# --- Docker Swarm ---

REGISTRY ?= localhost:5000
WORKERS  ?= 2
ENV_FILE ?= .env
SWARM_VARS = REGISTRY CERTBOT_DOMAIN CERTBOT_EMAIL NFS_SERVER_IP WORKER_CPU_LIMIT WORKER_MEMORY_LIMIT WORKER_CPU_RESERVATION WORKER_MEMORY_RESERVATION
SWARM_ENV = ENV_FILE="$(ENV_FILE)" $(foreach v,$(SWARM_VARS),$(v)="$(shell grep '^$(v)=' $(ENV_FILE) | head -1 | cut -d= -f2-)")

start-swarm:
	env $(SWARM_ENV) envsubst < docker-compose.swarm.yml | docker stack deploy -c - --with-registry-auth validate

start-swarm-nodb:
	env $(SWARM_ENV) envsubst < docker-compose.swarm.nodb.yml | docker stack deploy -c - --with-registry-auth validate

start-swarm-local:
	env $(SWARM_ENV) envsubst < docker-compose.swarm.yml > /tmp/_swarm.yml && \
	env $(SWARM_ENV) envsubst < docker-compose.swarm.local.yml > /tmp/_swarm.local.yml && \
	docker stack deploy -c /tmp/_swarm.yml -c /tmp/_swarm.local.yml --with-registry-auth validate && \
	rm -f /tmp/_swarm.yml /tmp/_swarm.local.yml

stop-swarm:
	docker stack rm validate

scale-workers:
	docker service scale validate_worker=$(WORKERS)

set-worker-limits:
	docker service update \
		$(if $(CPU),--limit-cpu $(CPU)) \
		$(if $(MEM),--limit-memory $(MEM)) \
		$(if $(CPU_RES),--reserve-cpu $(CPU_RES)) \
		$(if $(MEM_RES),--reserve-memory $(MEM_RES)) \
		validate_worker

swarm-push: build
	docker tag buildingsmart/validationsvc-backend $(REGISTRY)/validationsvc-backend
	docker tag buildingsmart/validationsvc-frontend $(REGISTRY)/validationsvc-frontend
	docker push $(REGISTRY)/validationsvc-backend
	docker push $(REGISTRY)/validationsvc-frontend

swarm-status:
	@docker service ls
	@echo "---"
	@docker service ps validate_worker

# Add a worker node to the Swarm cluster
# Usage: make add-worker NAME=dev-vm-worker-1 ENV_FILE=.env.DEV_SWARM
# Reads SWARM_WORKER_N entries and SWARM_SSH_USER from ENV_FILE
add-worker:
	@test -n "$(NAME)" || (echo "Usage: make add-worker NAME=<worker-name> ENV_FILE=.env.DEV_SWARM" && exit 1)
	$(eval SSH_USER := $(shell grep '^SWARM_SSH_USER=' $(ENV_FILE) | head -1 | cut -d= -f2-))
	$(eval MANAGER_IP := $(shell grep '^NFS_SERVER_IP=' $(ENV_FILE) | head -1 | cut -d= -f2-))
	$(eval WORKER_IP := $(shell grep '^SWARM_WORKER_' $(ENV_FILE) | grep '$(NAME)' | head -1 | cut -d: -f2))
	@test -n "$(WORKER_IP)" || (echo "ERROR: Worker '$(NAME)' not found in $(ENV_FILE). Add it as: SWARM_WORKER_N=$(NAME):<ip>" && exit 1)
	@test -n "$(MANAGER_IP)" || (echo "ERROR: NFS_SERVER_IP not set in $(ENV_FILE)" && exit 1)
	@test -n "$(SSH_USER)" || (echo "ERROR: SWARM_SSH_USER not set in $(ENV_FILE)" && exit 1)
	@echo "==> Installing Docker on $(NAME) ($(WORKER_IP))..."
	sudo -u $(SSH_USER) ssh -o StrictHostKeyChecking=no $(SSH_USER)@$(WORKER_IP) "curl -fsSL https://get.docker.com | sh"
	@echo "==> Configuring insecure registry ($(MANAGER_IP):5000)..."
	sudo -u $(SSH_USER) ssh -o StrictHostKeyChecking=no $(SSH_USER)@$(WORKER_IP) 'echo '"'"'{ "insecure-registries": ["$(MANAGER_IP):5000"] }'"'"' | sudo tee /etc/docker/daemon.json && sudo systemctl restart docker'
	@echo "==> Joining Swarm..."
	sudo -u $(SSH_USER) ssh -o StrictHostKeyChecking=no $(SSH_USER)@$(WORKER_IP) "sudo docker swarm join --token $$(sudo docker swarm join-token worker -q) $(MANAGER_IP):2377"
	@echo "==> Done! Node list:"
	sudo docker node ls

# Remove a worker node from the Swarm cluster
# Usage: make remove-worker NAME=dev-vm-worker-1 ENV_FILE=.env.DEV_SWARM
remove-worker:
	@test -n "$(NAME)" || (echo "Usage: make remove-worker NAME=dev-vm-worker-1 ENV_FILE=.env.DEV_SWARM" && exit 1)
	$(eval SSH_USER := $(shell grep '^SWARM_SSH_USER=' $(ENV_FILE) | head -1 | cut -d= -f2-))
	$(eval WORKER_IP := $(shell grep '^SWARM_WORKER_' $(ENV_FILE) | grep '$(NAME)' | head -1 | cut -d: -f2))
	@echo "==> Draining $(NAME)..."
	sudo docker node update --availability drain $(NAME)
	@echo "==> Leaving swarm..."
	-sudo -u $(SSH_USER) ssh -o StrictHostKeyChecking=no $(SSH_USER)@$(WORKER_IP) "sudo docker swarm leave"
	@echo "==> Waiting for node to go down..."
	@for i in 1 2 3 4 5 6; do sleep 5; sudo docker node ls --format '{{.Hostname}} {{.Status}}' | grep -q '$(NAME) Down' && break; echo "    waiting..."; done
	@echo "==> Removing node..."
	sudo docker node rm $(NAME)
	@echo "==> Done! Don't forget to remove the SWARM_WORKER entry from $(ENV_FILE)"
	sudo docker node ls

build:
	docker compose build \
	--build-arg GIT_COMMIT_HASH="$$(git rev-parse --short HEAD)" \
	--build-arg VERSION="$$(cat .VERSION)"

rebuild: clean
	docker compose build --no-cache \
	--build-arg GIT_COMMIT_HASH="$$(git rev-parse --short HEAD)" \
	--build-arg VERSION="$$(cat .VERSION)"

rebuild-frontend:
	docker stop frontend || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-frontend:latest' | uniq) || true
	docker compose build \
	--build-arg GIT_COMMIT_HASH="$$(git rev-parse --short HEAD)" \
	--build-arg VERSION="$$(cat .VERSION)"

rebuild-backend:
	docker stop backend || true
	docker stop worker || true
	docker stop scheduler || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-backend:latest' | uniq) || true
	docker compose build \
	--build-arg GIT_COMMIT_HASH="$$(git rev-parse --short HEAD)" \
	--build-arg VERSION="$$(cat .VERSION)"

clean:
	docker stop backend || true
	docker stop worker || true
	docker stop scheduler || true
	docker stop frontend || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-frontend:latest' | uniq) || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-backend:latest' | uniq) || true
	docker image prune --all --force --filter=label=org.opencontainers.image.vendor="buildingSMART.org"
	docker system prune --all --force --volumes --filter=label=org.opencontainers.image.vendor="buildingSMART.org"	

clean-all:
	docker stop backend || true
	docker stop worker || true
	docker stop scheduler || true
	docker stop frontend || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-frontend' | uniq) || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-backend' | uniq) || true
	docker image prune --all --force --filter=label=org.opencontainers.image.vendor="buildingSMART.org"
	docker system prune --all --force --volumes --filter=label=org.opencontainers.image.vendor="buildingSMART.org"	

fetch-modules:
	git submodule update --init --recursive
	git submodule foreach git clean -f .
	git submodule foreach git reset --hard
	git submodule update --remote --recursive

# runs end-to-end tests against a local instance of the Validation Service DB
e2e-test: start-infra
	cd e2e && npm install && npm run install-playwright && npm run test

e2e-test-report: start-infra
	cd e2e && npm install && npm run inst1all-playwright && npm run test:html && npm run test:report

BRANCH   ?= main                 
SUBTREES := \
    backend/apps/ifc_validation/checks/ifc_gherkin_rules \
    backend/apps/ifc_validation/checks/ifc_gherkin_rules/ifc_validation_models \
    backend/apps/ifc_validation_models

# Pulls the specified branch (default: 'main') for the main repo and all relevant submodules. 
# The default branch is main unless specified otherwise (e.g. 'make checkout BRANCH=development')
.PHONY: checkout
checkout:
	@echo "==> root repo   (branch: $(BRANCH))"
	@git checkout -q $(BRANCH) && git pull

	@echo "==> sub-repos   (branch: $(BRANCH))"
	@set -e; for d in $(SUBTREES); do \
	    echo "   → $$d"; \
	    ( cd $$d && git checkout -q $(BRANCH) && git pull ); \
	done

	@echo "==> signatures/store (always on main)"
	@( cd backend/apps/ifc_validation/checks/signatures/store && \
	   git checkout -q main && git pull )