.PHONY: env up down observability mapper mapping-check test logs e2e migrate prod-config

env:
	@test -f .env || cp .env.example .env

up: env
	docker compose up --build -d

# Apply database migrations by hand (`make up` already does this on every start).
migrate: env
	docker compose run --rm migrate

# Check the production compose file against the example settings. Uses a temporary deploy/.env
# if there is none, and never removes one that was already there.
prod-config:
	@created=0; test -f deploy/.env || { cp deploy/.env.production.example deploy/.env; created=1; }; \
	docker compose -f deploy/docker-compose.prod.yml --profile mapping --profile vision config -q; r=$$?; \
	if [ $$created = 1 ]; then rm deploy/.env; fi; exit $$r

# The photogrammetry worker (large image, slow first build): needed for "Build map" jobs.
mapper: env
	docker compose --profile mapping up --build -d mapper

# Reads photos of seed packets (Seeds > Scan packets); CPU only, on its own queue.
vision: env
	docker compose --profile vision up --build -d vision

# Builds synthetic scenes (photos only, then photos plus a walk-through video), runs them through the
# real pipeline and checks the results are in the right place and shape (needs `make up mapper`;
# takes several minutes).
mapping-check:
	python3 scripts/mapping_check.py
	SCENARIO=video python3 scripts/mapping_check.py

observability: env
	docker compose --profile observability up --build -d

down:
	docker compose --profile observability --profile mapping --profile vision down

test: env
	docker compose run --rm --no-deps api pytest -q

logs:
	docker compose logs -f api worker

# End-to-end browser tests (Playwright in Docker, against the running compose stack).
e2e: up
	docker run --rm --network $$(basename $$(pwd) | tr 'A-Z' 'a-z')_default -v $$(pwd)/e2e:/e2e -w /e2e \
		mcr.microsoft.com/playwright:v1.64.1-noble sh -c "npm ci && npx playwright test"
