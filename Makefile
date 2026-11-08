# Code Battles: day-to-day commands. `make help` lists them.
# Targets act on the machine where you run make (laptop: dev stack; server: production stack).
# Only `deploy` and `rollback` go over ssh. On the server the presence of .last_good_tag makes
# every target use the production compose files and that image tag.
SERVER      ?= ubuntu@your-server
DEPLOY_PATH ?= ~/arthur/code_battles

ifneq ($(wildcard .last_good_tag),)
export TAG ?= $(shell cat .last_good_tag)
export COMPOSE_FILE ?= compose.yaml:deploy/compose.prod.yaml
endif

DC = docker compose
MANAGE = $(DC) exec -T django python manage.py

.DEFAULT_GOAL := help
.PHONY: help up down logs shell test lint migrate migration build deploy rollback backup restore \
        update-deps createsuperuser manage import-tasks sandbox-images expire-battles flush-tokens

help: ## this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/' | sort

up: ## build and start the stack, wait until healthy
	$(DC) up -d --build --wait

down: ## stop the stack (data volumes stay)
	$(DC) down

logs: ## follow logs: make logs [s=django]
	$(DC) logs -f --tail=100 $(s)

shell: ## shell in the django container
	$(DC) exec django bash

test: ## Django + FastAPI tests against throwaway postgres/redis (needs uv)
	bash scripts/test.sh

lint: ## ruff for both backends, eslint for the frontend
	cd backend && uv run ruff check --select F,E9,B .
	cd fastapi_app && uv run ruff check --select F,E9,B .
	cd frontend && npm run lint

migrate: ## apply migrations (the one-shot migrate service)
	$(DC) run --rm migrate

migration: ## create a migration on the host: make migration name=add_x (needs backend/.env)
	@test -n "$(name)" || { echo "usage: make migration name=<name>"; exit 1; }
	cd backend && uv run python manage.py makemigrations -n $(name)

build: ## build all images, sandbox images included
	$(DC) --profile build-only build

deploy: ## rsync to the server and run deploy/deploy.sh there
	rsync -az --human-readable --exclude=.env --exclude=.env.qa --exclude=.git --exclude=node_modules \
	  --exclude=.venv --exclude=/env --exclude=logs --exclude=dist --exclude=frontend_debug \
	  --exclude=backups --exclude=.last_good_tag --exclude=__pycache__ --exclude=.pytest_cache \
	  --exclude=.ruff_cache --exclude=.idea --exclude=redis_data --exclude=backend/staticfiles \
	  --include=backend/tests/tests.json ./ $(SERVER):$(DEPLOY_PATH)/
	ssh $(SERVER) 'cd $(DEPLOY_PATH) && bash deploy/deploy.sh'

rollback: ## server back to .last_good_tag (or: make rollback tag=20261029-101500)
	ssh $(SERVER) 'cd $(DEPLOY_PATH) && bash deploy/rollback.sh $(tag)'

backup: ## pg_dump into backups/ (7 daily + 4 weekly)
	bash scripts/backup.sh

restore: ## restore a dump: make restore file=backups/daily/code_battles-....dump (replaces the data!)
	@test -f "$(file)" || { echo "usage: make restore file=<dump>"; exit 1; }
	$(DC) stop web django fastapi
	$(DC) exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < "$(file)"
	$(DC) up -d --wait

update-deps: ## upgrade lock files (python, npm), then audit
	cd backend && uv lock --upgrade && uv sync --frozen
	cd fastapi_app && uv lock --upgrade && uv sync --frozen
	cd frontend && npm update && npm audit --omit=dev || true
	cd backend && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/cb-backend-req.txt >/dev/null && uvx pip-audit -r /tmp/cb-backend-req.txt --no-deps --disable-pip
	cd fastapi_app && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/cb-fastapi-req.txt >/dev/null && uvx pip-audit -r /tmp/cb-fastapi-req.txt --no-deps --disable-pip

createsuperuser: ## admin user for /admin/
	$(DC) exec django python manage.py createsuperuser

manage: ## any manage.py command: make manage cmd="showmigrations"
	$(MANAGE) $(cmd)

import-tasks: ## load backend/tests/tests.json into the database (safe to repeat)
	$(DC) --profile tools run --rm import-tasks

sandbox-images: ## build the sandbox images (the runner never pulls them)
	$(DC) --profile build-only build sandbox-python sandbox-cpp

expire-battles: ## close pending battles that waited too long (cron: hourly)
	$(MANAGE) expire_pending_battles

flush-tokens: ## delete expired JWT blacklist rows (cron: daily)
	$(MANAGE) flushexpiredtokens
