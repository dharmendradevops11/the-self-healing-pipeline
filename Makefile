# Everyday commands. Run `make help`.
PY ?= .venv/bin/python
.DEFAULT_GOAL := help

# Docker Desktop ships `docker compose`; Colima and older installs use `docker-compose`.
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo 'docker compose' || echo docker-compose)

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  %-14s %s\n",$$1,$$2}'

venv:           ## Create the Python 3.11 environment (needs uv: https://docs.astral.sh/uv/)
	uv venv --python 3.11 .venv
	uv pip install --python $(PY) -r requirements-dev.txt
	uv pip install --python $(PY) -e .

test:           ## Run the unit tests (no AWS, no Docker)
	$(PY) -m pytest

lint:           ## Lint and type-check
	$(PY) -m ruff check healer tests infra
	$(PY) -m mypy healer infra

demo:           ## Run the whole pipeline on your laptop (offline, no AWS)
	$(PY) -m healer.demo

local-up:       ## Start LocalStack (Chapter 17, "Start Local")
	$(COMPOSE) up -d localstack

local-down:     ## Stop LocalStack
	$(COMPOSE) down

local-test:     ## Run the LocalStack integration tests
	$(PY) -m pytest -m integration

clean:          ## Remove caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache cdk.out
	find . -name __pycache__ -prune -exec rm -rf {} +

.PHONY: help demo venv test lint local-up local-down local-test clean
