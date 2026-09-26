.PHONY: up up-detached down down-clean logs shell web-shell db-shell migrate reset build accept accept-fresh

COMPOSE ?= docker compose
PYTHON  ?= python3

up:
	$(COMPOSE) up --build

up-detached:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

down-clean:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec web bash

web-shell:
	$(COMPOSE) exec web python manage.py shell

db-shell:
	$(COMPOSE) exec db psql -U dogfood -d dogfood

migrate:
	$(COMPOSE) exec web python manage.py migrate

reset:
	$(COMPOSE) down -v
	$(COMPOSE) up --build

build:
	$(COMPOSE) build

# Wired up at G2 once acceptance.py exists.
accept:
	@echo "acceptance target pending G2 — acceptance.py is published alongside run.py"

accept-fresh:
	@echo "acceptance target pending G2"
