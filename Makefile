.DEFAULT_GOAL := help
sources = council_of_sages tests scripts

# Docker commands
DOCKER_COMPOSE := docker compose
DOCKER_BUILD_ARGS := --progress=plain

# Python version check using uv
PYTHON_VERSION_CHECK := uv run python -c "import sys; exit(0) if sys.version_info >= (3, 13) else (print('Python 3.13+ is required', file=sys.stderr) or exit(1))"

# Export environment variables for the current shell
EXPORT_ENVS = export $$(< .env) > /dev/null 2>&1

.PHONY: help  ## Display this message
help:
	@grep -E \
		'^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | \
		sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-19s\033[0m %s\n", $$2, $$3}'

.PHONY: check-deps  ## Check system dependencies
check-deps:
	@echo "Checking system dependencies..."
	@docker --version >/dev/null 2>&1 || (echo "Docker is required" && exit 1)
	@docker compose version >/dev/null 2>&1 || (echo "Docker Compose is required" && exit 1)
	@uv --version >/dev/null 2>&1 || (echo "Please install uv: https://docs.astral.sh/uv/getting-started/installation/" && exit 1)
	@$(PYTHON_VERSION_CHECK)
	@pre-commit -V >/dev/null 2>&1 || (echo "Please install pre-commit: https://pre-commit.com/" && exit 1)
	@echo "All system dependencies are satisfied"

.PHONY: install  ## Install the package, dependencies, and pre-commit hooks
install:
	@uv venv --python 3.13
	@uv pip install -e ".[dev,linting,testing]"
	pre-commit install --install-hooks

.PHONY: sync  ## Sync dependencies and lockfiles
sync:
	uv pip install -e . --force-reinstall
	uv sync

.PHONY: format  ## Auto-format python source files
format:
	@uv run ruff format .
	@uv run ruff check --fix .

.PHONY: lint  ## Run all linters (ruff, mypy)
lint:
	@uv run ruff format --check .
	@uv run ruff check .
	@uv run mypy $(sources)

.PHONY: test  ## Run tests with coverage report
test:
	uv run pytest && \
	uv run coverage html && \
	uv run coverage xml -o coverage/coverage.xml

.PHONY: spellcheck  ## Run codespell to check spelling
spellcheck:
	pre-commit run codespell --all-files

.PHONY: check-all  ## Run all code quality checks
check-all: lint spellcheck test

.PHONY: build  ## Build Docker images
build:
	$(DOCKER_COMPOSE) build $(DOCKER_BUILD_ARGS)

.PHONY: build-prod  ## Build production Docker image
build-prod:
	docker build $(DOCKER_BUILD_ARGS) \
		--target production \
		-t council-of-sages:latest .

.PHONY: up  ## Start all services in Docker
up:
	$(DOCKER_COMPOSE) up -d

.PHONY: down  ## Stop all services
down:
	$(DOCKER_COMPOSE) down

.PHONY: logs  ## View logs from all services
logs:
	$(DOCKER_COMPOSE) logs -f

.PHONY: ps  ## List running services
ps:
	$(DOCKER_COMPOSE) ps

.PHONY: clean  ## Stop all services and clean up volumes/cache
clean: down
	$(DOCKER_COMPOSE) down -v
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name '*.py[co]' -exec rm -f {} +
	find . -type f -name '*~' -exec rm -f {} +
	find . -type f -name '.*~' -exec rm -f {} +
	rm -rf .cache .pytest_cache .ruff_cache htmlcov
	rm -rf *.egg-info build dist site
	rm -rf .coverage .coverage.* coverage
	rm -rf .venv

.PHONY: db  ## Start the database (if using MongoDB)
db: check-deps
	$(DOCKER_COMPOSE) up -d mongodb

.PHONY: dev  ## Run the service with auto-reload
dev: db
	$(EXPORT_ENVS)
	uv run uvicorn council_of_sages.app:app --reload --host 0.0.0.0 --port 8080

.PHONY: run  ## Run the service without auto-reload
run: up
	trap 'make down' EXIT; \
	python -m council_of_sages.app

.PHONY: shell  ## Open a shell in the running app container
shell:
	$(DOCKER_COMPOSE) exec app /bin/bash
