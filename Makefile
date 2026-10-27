.PHONY: env up down observability test logs

env:
	@test -f .env || cp .env.example .env

up: env
	docker compose up --build -d

observability: env
	docker compose --profile observability up --build -d

down:
	docker compose --profile observability down

test: env
	docker compose run --rm --no-deps api pytest -q

logs:
	docker compose logs -f api worker
