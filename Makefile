.PHONY: env up down observability mapper mapping-check test logs e2e

env:
	@test -f .env || cp .env.example .env

up: env
	docker compose up --build -d

# The photogrammetry worker (large image, slow first build): needed for "Build map" jobs.
mapper: env
	docker compose --profile mapping up --build -d mapper

# Builds a synthetic scene, runs it through the real pipeline and checks the result is in the right
# place and shape (needs `make up mapper`; takes several minutes).
mapping-check:
	python3 scripts/mapping_check.py

observability: env
	docker compose --profile observability up --build -d

down:
	docker compose --profile observability --profile mapping down

test: env
	docker compose run --rm --no-deps api pytest -q

logs:
	docker compose logs -f api worker

# End-to-end browser tests (Playwright in Docker, against the running compose stack).
e2e: up
	docker run --rm --network $$(basename $$(pwd) | tr 'A-Z' 'a-z')_default -v $$(pwd)/e2e:/e2e -w /e2e \
		mcr.microsoft.com/playwright:v1.64.1-noble sh -c "npm ci && npx playwright test"
