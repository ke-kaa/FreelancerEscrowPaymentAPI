.DEFAULT_GOAL := help
SHELL := /bin/bash

PY := uv run python
MANAGE := $(PY) manage.py

# ─── Setup ────────────────────────────────────────────────────────────────────
.PHONY: install
install:  ## Install base + development dependencies
	uv sync --group development

.PHONY: install-prod
install-prod:  ## Install base + production dependencies
	uv sync --group production

.PHONY: lock
lock:  ## Refresh uv.lock
	uv lock

# ─── Django ───────────────────────────────────────────────────────────────────
.PHONY: run
run:  ## Run development server on :8000
	$(MANAGE) runserver 0.0.0.0:8000

.PHONY: shell
shell:  ## Open Django shell (ipython if installed)
	$(MANAGE) shell

.PHONY: dbshell
dbshell:  ## Open Postgres shell
	$(MANAGE) dbshell

.PHONY: check
check:  ## Run manage.py check
	$(MANAGE) check

.PHONY: migrate
migrate:  ## Apply database migrations
	$(MANAGE) migrate

.PHONY: makemigrations
makemigrations:  ## Generate migrations from model changes
	$(MANAGE) makemigrations

.PHONY: migrations-plan
migrations-plan:  ## Show migration plan
	$(MANAGE) migrate --plan

.PHONY: superuser
superuser:  ## Create admin user
	$(MANAGE) createsuperuser

.PHONY: collectstatic
collectstatic:  ## Collect static files
	$(MANAGE) collectstatic --noinput

# ─── Celery ───────────────────────────────────────────────────────────────────
.PHONY: worker
worker:  ## Run Celery worker
	uv run celery -A config worker -l info

.PHONY: beat
beat:  ## Run Celery beat scheduler
	uv run celery -A config beat -l info

# ─── Quality ──────────────────────────────────────────────────────────────────
.PHONY: test
test:  ## Run pytest
	DJANGO_SETTINGS_MODULE=config.settings.testing uv run pytest

.PHONY: test-cov
test-cov:  ## Run pytest with coverage
	DJANGO_SETTINGS_MODULE=config.settings.testing uv run pytest --cov=src --cov-report=term-missing

.PHONY: lint
lint:  ## Ruff lint
	uv run ruff check .

.PHONY: format
format:  ## Ruff format
	uv run ruff format .

.PHONY: typecheck
typecheck:  ## Mypy type-check src/
	uv run mypy src/

.PHONY: qa
qa: lint typecheck test  ## Run lint + typecheck + tests

# ─── Cleanup ──────────────────────────────────────────────────────────────────
.PHONY: clean
clean:  ## Remove caches, pyc, coverage artifacts
	find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -not -path "./.venv/*" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov

# ─── Help ─────────────────────────────────────────────────────────────────────
.PHONY: help
help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
