VERSION=v0.6.0-alpha

none:
	@echo ERROR: Enter at least one target (start, start-load-balanced, start-full, start-infra-only, stop, build, rebuild, clean, fetch-modules)

# minimal setup (w/o observability/scaling etc...)
start:
	docker compose -f docker-compose.yml up -d

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
	docker compose build

rebuild: clean
	docker compose build --no-cache

rebuild-frontend:
	docker stop frontend || true
	docker rmi --force buildingsmart/validationsvc-frontend:${VERSION}
	docker compose build

rebuild-backend:
	docker stop backend || true
	docker stop worker || true
	docker rmi --force buildingsmart/validationsvc-backend:${VERSION}
	docker compose build

clean:
	docker compose down
	docker image prune --force
	docker system prune --all --force --volumes --filter=label=org.opencontainers.image.vendor="buildingSMART.org"	

fetch-modules:
	git submodule update --init --recursive
	git submodule update --remote