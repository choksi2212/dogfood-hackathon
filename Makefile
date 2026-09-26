.PHONY: up up-detached down down-clean logs shell web-shell db-shell migrate reset build seed seed-fresh accept accept-fresh

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

seed:
	$(COMPOSE) exec -T web python manage.py seed_fixtures

reset:
	$(COMPOSE) down -v
	$(COMPOSE) up --build

build:
	$(COMPOSE) build

# Run the seven-check acceptance suite. Writes acceptance-report.txt and
# pipes it to stdout so you see the result immediately.
accept:
	$(COMPOSE) exec -T web python acceptance.py .dogfood.toml | tee acceptance-report.txt

# Like accept, but also re-seeds first so the report reflects a known
# fresh state. Useful right before a submission.
accept-fresh: seed
	$(COMPOSE) exec -T web python acceptance.py .dogfood.toml | tee acceptance-report.txt

# Test suite — 15 categories, each with its own subdirectory + docs.
# conftest.py + pytest.ini are shared (read-only).
test:
	$(COMPOSE) exec -T web pytest tests/ -v

# Single category: make test-smoke, make test-auth, make test-roles, ...
test-%:
	$(COMPOSE) exec -T web pytest tests/$*/ -v

# Coverage report (HTML into reports/).
test-cov:
	$(COMPOSE) exec -T web pytest tests/ --cov=apps --cov-report=html --cov-report=term-missing
	@echo "HTML coverage: reports/htmlcov/index.html"
