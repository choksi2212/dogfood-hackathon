.PHONY: up up-detached up-all down down-clean logs shell web-shell db-shell migrate reset build seed seed-fresh accept accept-fresh accept-ci ci lint test test-% test-cov types metrics-up metrics-down metrics-logs metrics-status

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
	$(COMPOSE) exec -T web python manage.py import_fixtures

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

# Type safety (mypy + django-stubs + djangorestframework-stubs).
# Strict on the new code (apps.observability, apps.billing); lax on
# legacy apps until each gets annotated.
types:
	$(COMPOSE) exec -T web mypy apps/ --config-file mypy.ini
# CI-friendly acceptance runner. No docker compose; runs the script
# directly against whichever server the caller has already started
# (the GitHub Actions acceptance workflow starts `manage.py runserver`
# in the background and then calls this). Honors $DOGFOOD_CONFIG if
# you want to point at a non-default .dogfood.*.toml.
accept-ci:
	@if [ -n "$$DOGFOOD_CONFIG" ]; then \
		echo "Running acceptance against $$DOGFOOD_CONFIG"; \
		python acceptance.py "$$DOGFOOD_CONFIG"; \
	else \
		echo "Running acceptance against .dogfood.toml"; \
		python acceptance.py .dogfood.toml; \
	fi

# `make ci` is what a developer runs locally to mirror the GitHub
# Actions pipeline: ruff check + ruff format --check + pytest.
# The acceptance suite is intentionally NOT here — it needs a live
# server. Run it explicitly via `make accept` (docker compose) or
# `make accept-ci` against an already-running `runserver`.
ci: lint
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	python manage.py migrate --noinput
	pytest tests/ -v --tb=short

# ruff check + ruff format --check. Used by `make ci` and by the
# lint GitHub Actions workflow.
lint:
	@command -v ruff >/dev/null 2>&1 || pip install ruff==0.6.9
	ruff check .
	ruff format --check .

# --- Observability stack ---------------------------------------------------
# `make up` already brings up the full stack (web + db + nginx +
# frontend + prometheus + grafana + alertmanager). These targets let
# you operate on just the metrics pipeline.
metrics-up:
	$(COMPOSE) up --build -d prometheus alertmanager grafana

metrics-down:
	$(COMPOSE) stop prometheus alertmanager grafana

metrics-logs:
	$(COMPOSE) logs -f prometheus alertmanager grafana

metrics-status:
	@echo "== Prometheus =="
	@curl -fsS http://127.0.0.1:9090/-/healthy 2>/dev/null && echo " (healthy)" || echo " (down)"
	@echo "== Grafana =="
	@curl -fsS http://127.0.0.1:3000/api/health 2>/dev/null && echo " (healthy)" || echo " (down)"
	@echo "== Alertmanager =="
	@curl -fsS http://127.0.0.1:9093/-/healthy 2>/dev/null && echo " (healthy)" || echo " (down)"

# Bring up the entire stack (backend + frontend + observability) and
# report the public entry points.
up-all: up-detached metrics-status seed
	@echo
	@echo "Portal:        http://127.0.0.1:8000/"
	@echo "API base:      http://127.0.0.1:8000/api/"
	@echo "Grafana:       http://127.0.0.1:8000/grafana/  (admin / admin)"
	@echo "Prometheus:    http://127.0.0.1:8000/prometheus/"
	@echo "Alertmanager:  http://127.0.0.1:8000/alertmanager/"
