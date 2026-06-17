# Postiz one-word operations. Run from the postiz/ folder, e.g. `make up`.
# Server ops assume Docker + the .env file are present (see README.md).

COMPOSE ?= docker compose
PY      ?= python3
CONTENT ?= automation/content/hp-landscaping.json
PLANNED ?= automation/planned.json

.PHONY: help up down restart logs update backup ps \
        dry-run plan schedule

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

## --- Server lifecycle ---
up: ## Start Postiz (detached)
	$(COMPOSE) up -d
down: ## Stop Postiz (keeps data)
	$(COMPOSE) down
restart: ## Restart Postiz
	$(COMPOSE) restart
ps: ## Show container status
	$(COMPOSE) ps
logs: ## Tail Postiz logs
	$(COMPOSE) logs -f postiz
update: ## Pull latest image and recreate
	$(COMPOSE) pull && $(COMPOSE) up -d
backup: ## Dump the Postgres database to backup.sql
	docker exec postiz-postgres pg_dump -U postiz-user postiz-db-local > backup.sql
	@echo "Wrote backup.sql"

## --- Content automation (set CONTENT=... to choose a file) ---
dry-run: ## Preview API payloads without sending (CONTENT=...)
	$(PY) automation/schedule_posts.py $(CONTENT) --dry-run
plan: ## Build a Mon/Wed/Fri 9am calendar -> PLANNED (CHANNELS=id required)
	$(PY) automation/plan_calendar.py $(CONTENT) --channels $(CHANNELS) --out $(PLANNED)
schedule: ## Send PLANNED posts to Postiz (needs POSTIZ_API_URL/KEY env)
	$(PY) automation/schedule_posts.py $(PLANNED)
