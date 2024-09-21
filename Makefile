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
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-backend:latest' | uniq) || true
	docker compose build \
	--build-arg GIT_COMMIT_HASH="$$(git rev-parse --short HEAD)" \
	--build-arg VERSION="$$(cat .VERSION)"

clean:
	docker stop backend || true
	docker stop worker || true
	docker stop frontend || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-frontend:latest' | uniq) || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-backend:latest' | uniq) || true
	docker image prune --all --force --filter=label=org.opencontainers.image.vendor="buildingSMART.org"
	docker system prune --all --force --volumes --filter=label=org.opencontainers.image.vendor="buildingSMART.org"	

clean-all:
	docker stop backend || true
	docker stop worker || true
	docker stop frontend || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-frontend' | uniq) || true
	docker rmi --force $$(docker images -q 'buildingsmart/validationsvc-backend' | uniq) || true
	docker image prune --all --force --filter=label=org.opencontainers.image.vendor="buildingSMART.org"
	docker system prune --all --force --volumes --filter=label=org.opencontainers.image.vendor="buildingSMART.org"	

fetch-modules:
	git submodule update --init --recursive
	git submodule update --remote