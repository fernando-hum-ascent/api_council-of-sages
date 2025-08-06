# FastAPI + LangGraph Project Setup Guide

This guide provides comprehensive instructions for setting up a FastAPI + LangGraph project with modern Python tooling. Use this as a reference to generate all necessary configuration files and scripts.

## Project Structure

```
project-name/
├── pyproject.toml           # Python project configuration
├── Makefile                # Development commands
├── Dockerfile              # Container configuration
├── docker-compose.yaml     # Local development services
├── .python-version         # Python version specification
├── ruff.toml               # Code formatting and linting
├── .pre-commit-config.yaml # Git hooks configuration
├── .gitignore              # Git ignore patterns
├── .dockerignore           # Docker ignore patterns
├── README.md               # Project documentation
├── your_project_name/      # Main application package
│   ├── __init__.py
│   ├── app.py              # FastAPI application entry point
│   ├── config.py           # Configuration management
│   ├── types.py            # Pydantic models and enums
│   ├── exc.py              # Custom exceptions
│   ├── resources/          # API endpoints (plural names)
│   ├── lib/                # Services and shared logic
│   ├── models/             # Database models (if using)
│   └── tasks/              # Background tasks
├── tests/                  # Test suite
├── scripts/                # Utility scripts
└── evals/                  # LLM evaluations (optional)
```

## Required Files and Configurations

### 1. Python Version Management

**File: `.python-version`**
```
3.13
```

**Purpose**: Specifies Python version for pyenv and other version managers.

### 2. Project Configuration

**File: `pyproject.toml`**
```toml
[project]
name = "your-project-name"
version = "0.1.0"
authors = [
    { name = "Luis Fernando Garcia Cabrera", email = "fernando@hum-ascent.com" },
]
description = "FastAPI + LangGraph application"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "httpx>=0.25.0",
    "pydantic>=2.4.2",
    "pydantic-settings>=2.1.0",
    "pydantic-core>=2.24.0",
    "python-dotenv>=1.0.0",
    "loguru>=0.7.2",
    "langgraph>=0.0.20",
    "langchain>=0.3.12",
    "langchain-core>=0.3.25",
    "langchain-community>=0.3.12",
    "langchain-openai>=0.2.12",
    "langchain-anthropic>=0.3.1",
    "emoji>=2.14.1",
    "blinker>=1.9.0",
    "mongoengine-plus>=1.0.0",  # Optional: if using MongoDB
]

[dependency-groups]
dev = [
    "ipython",
    "ipdb",
    "ipykernel",
    "pre-commit>=4.0.1",
]
linting = [
    "ruff>=0.11.9",
    "mypy>=1.15.0",
    "types-requests>=2.31.0.20240125",
    "types-PyYAML>=6.0.12.12",
]
testing = [
    "pytest>=7.4.4",
    "coverage>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.25.0",
    "pytest-loguru>=0.4.0",
    "vcrpy>=2.31.0",
    "pytest-vcr>=1.0.2",
    "mongomock>=4.3.0",  # Optional: if using MongoDB
    "defusedxml>=0.7.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
addopts = "--ignore=__pypackages__ --ignore-glob=*.yaml -v --durations=10 --cov=your_project_name --cov-report=term-missing"
asyncio_mode = "auto"
filterwarnings = [
    "ignore:datetime.datetime.utcfromtimestamp\\(\\) is deprecated:DeprecationWarning",
    "ignore:datetime.datetime.utcnow\\(\\) is deprecated:DeprecationWarning",
]

[tool.mypy]
ignore_missing_imports = true
plugins = "pydantic.mypy"

[tool.hatch.build.targets.wheel]
packages = ["your_project_name"]

[tool.coverage.report]
exclude_also = [
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

### 3. Code Formatting and Linting

**File: `ruff.toml`**
```toml
line-length = 79
target-version = "py313"
indent-width = 4
exclude = [
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "docker-compose.yml",
]

[format]

[lint]
select = [
    "N",      # pep8-naming
    "ANN",    # flake8-annotations
    "ASYNC",  # flake8-async
    "FAST",   # FastApi
    "S",      # flake8-bandit
    "BLE",    # flake8-blind-except
    "T20",    # flake8-print
    "B",      # flake8-bugbear
    "F",      # Pyflakes
    "I",      # isort
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "UP",     # pyupgrade
    "A",      # builtins
    "ERA",    # erradicate
    "C4",     # flake8-comprehensions
]

ignore = [
    "ANN401",  # Allow using Any as type hint
    "S101",    # Allow using assert
    "B904",    # Allow raising exceptions without "from err"
    "W191",    # Ruff conflicting rules
    "E111",
    "E114",
    "E117",
]

[lint.per-file-ignores]
"conftest.py" = ["S"]
"test_*.py" = ["S", "ANN201"]
"scripts/**/*.py" = ["T201"]

[lint.pep8-naming]
classmethod-decorators = ["pydantic.model_validator"]

[lint.flake8-annotations]
suppress-dummy-args = true
```

### 4. Pre-commit Hooks

**File: `.pre-commit-config.yaml`**
```yaml
repos:
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.6.0
  hooks:
  - id: check-yaml
  - id: check-toml
  - id: end-of-file-fixer
  - id: trailing-whitespace

- repo: https://github.com/codespell-project/codespell
  rev: v2.2.6
  hooks:
  - id: codespell
    additional_dependencies:
      - tomli

- repo: https://github.com/DavidAnson/markdownlint-cli2
  rev: v0.12.1
  hooks:
    - id: markdownlint-cli2

- repo: local
  hooks:
  - id: lint
    name: lint
    entry: make lint
    types: [python]
    language: system
    pass_filenames: false
```

### 5. Development Makefile

**File: `Makefile`**
```makefile
.DEFAULT_GOAL := help
sources = your_project_name tests scripts

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
		-t your-project:latest .

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
	uv run uvicorn your_project_name.app:app --reload --host 0.0.0.0 --port 8080

.PHONY: run  ## Run the service without auto-reload
run: up
	trap 'make down' EXIT; \
	python -m your_project_name.app

.PHONY: shell  ## Open a shell in the running app container
shell:
	$(DOCKER_COMPOSE) exec app /bin/bash
```

### 6. Docker Configuration

**File: `Dockerfile`**
```dockerfile
# syntax=docker/dockerfile:1.4

FROM python:3.13-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

# Clean up curl
RUN apt-get purge -y --auto-remove curl

# Development image
FROM base as development
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY your_project_name your_project_name/
RUN uv pip install --system -e ".[dev,linting,testing]"
COPY . .

# Production image
FROM base as production
COPY pyproject.toml ./
COPY your_project_name your_project_name/
RUN uv pip install --system .

# Create non-root user
RUN useradd -m -u 1000 app \
    && chown -R app:app /app
USER app

# Command to run the application
CMD ["python", "-m", "your_project_name.app"]
```

**File: `docker-compose.yaml`**
```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"

services:
  app:
    build:
      context: .
      target: development
    ports:
      - "8080:8080"
    volumes:
      - .:/app
      - python-packages:/app/__pypackages__
    environment:
      - ENV_FILE=.env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging: *default-logging
    depends_on:
      - mongodb

  mongodb:
    image: mongo:8.0
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: example
    ports:
      - '27017:27017'
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh mongodb://root:example@localhost:27017/admin --quiet
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
    logging: *default-logging

volumes:
  python-packages:
  mongodb_data:
```

### 7. Git Configuration

**File: `.gitignore`**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Project specific
.ruff_cache/
.mypy_cache/
.ipynb_checkpoints/
*.log
```

**File: `.dockerignore`**
```
.git
.gitignore
README.md
Dockerfile
.dockerignore
.venv
venv
__pycache__
.pytest_cache
.coverage
htmlcov
.ruff_cache
.mypy_cache
.env
tests
scripts
evals
*.md
.pre-commit-config.yaml
.python-version
ruff.toml
```

### 8. Environment Configuration

**File: `.env.example`**
```env
# Application
DEBUG=true
LOG_LEVEL=DEBUG
ENV=development

# API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Database
MONGODB_URL=mongodb://root:example@localhost:27017/your_db_name?authSource=admin
```

## System Requirements

### Required Tools
1. **Python 3.13+**: Use pyenv for version management
2. **uv**: Modern Python package manager and environment tool
3. **Docker**: For containerization and local services
4. **Docker Compose**: For multi-service local development
5. **pre-commit**: For git hooks and code quality

### Installation Commands
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install pre-commit
pip install pre-commit

# Or via homebrew on macOS
brew install uv pre-commit
```

## Project Initialization Steps

1. **Create project directory and files**:
   ```bash
   mkdir your-project-name
   cd your-project-name
   ```

2. **Initialize git repository**:
   ```bash
   git init
   ```

3. **Create all configuration files** from the templates above

4. **Set up Python environment**:
   ```bash
   make check-deps
   make install
   ```

5. **Create basic application structure**:
   ```bash
   mkdir -p your_project_name/{resources,lib,models,tasks}
   touch your_project_name/__init__.py
   ```

6. **Create environment file**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

7. **Test the setup**:
   ```bash
   make format
   make lint
   make test
   ```

## Development Workflow

### Option 1: Local Development with Docker Services (Recommended)

This is the most common approach for daily development - run your FastAPI app locally but use Docker for supporting services like MongoDB.

1. **Run your app locally with auto-reload**:
   ```bash
   make dev  # This will start MongoDB if not running, then start FastAPI locally
   ```

3. **Check running services**:
   ```bash
   make ps  # See what Docker services are running
   docker compose ps  # Alternative command
   ```

4. **View database logs if needed**:
   ```bash
   docker compose logs mongodb
   ```

5. **Stop services when done**:
   ```bash
   make down  # Stops all Docker services
   # or keep them running for next session
   ```

### Option 2: Everything in Docker

Run both your app and services in Docker (useful for testing the full containerized setup):

1. **Build and start everything**:
   ```bash
   make build  # Build Docker images
   make up     # Start all services (app + MongoDB)
   ```

2. **View logs from all services**:
   ```bash
   make logs   # Follow logs from all containers
   ```

3. **Access the running app container**:
   ```bash
   make shell  # Open bash in the app container
   ```

4. **Stop everything**:
   ```bash
   make down   # Stop all services
   ```

### Daily Development Commands Summary

```bash
# Quick start for daily development
make dev          # Start MongoDB + run FastAPI locally with auto-reload

# Check what's running
make ps           # List running Docker services

# Code quality (run before committing)
make format       # Auto-format code
make lint         # Check code quality
make test         # Run tests
make check-all    # Run all quality checks

# Database management
make db           # Start only MongoDB
docker compose logs mongodb  # View database logs

# Clean up (when needed)
make clean        # Stop services and clean up caches/volumes
```

### Docker Services Explained

The `docker-compose.yaml` defines these services:

1. **MongoDB** (`mongodb` service):
   - Runs on port `27017`
   - Username: `root`, Password: `example`
   - Data persisted in Docker volume `mongodb_data`
   - Accessible from your local app at `mongodb://root:example@localhost:27017/your_db_name?authSource=admin`

2. **App** (`app` service):
   - Only used when running everything in Docker (`make up`)
   - Runs on port `8080`
   - Auto-reloads code changes when volumes are mounted

### Managing Docker Services

**Start specific services**:
```bash
docker compose up -d mongodb        # Start only MongoDB
docker compose up -d mongodb redis  # Start MongoDB and Redis (if you add it)
```

**Check service health**:
```bash
docker compose ps                    # See all services status
docker compose logs mongodb         # View MongoDB logs
docker compose exec mongodb mongosh # Connect to MongoDB shell
```

**Clean up and reset**:
```bash
make clean                          # Remove containers and volumes
docker compose down -v              # Remove containers and volumes manually
docker volume ls                    # List Docker volumes
docker volume rm mongodb_data       # Remove specific volume (loses data!)

### Troubleshooting Docker Services

**Port conflicts**:
```bash
# Check what's using a port
lsof -i :27017
netstat -tulpn | grep 27017

# Change ports in docker-compose.yaml if needed
ports:
  - "27018:27017"  # Use different host port
```

**Permission issues**:
```bash
# Fix Docker permission issues (Linux)
sudo usermod -aG docker $USER
newgrp docker
```

**Database connection issues**:
```bash
# Test MongoDB connection
docker compose exec mongodb mongosh mongodb://root:example@localhost:27017/admin

# Check MongoDB is accessible from host
mongosh "mongodb://root:example@localhost:27017/your_db_name?authSource=admin"
```

**Reset everything**:
```bash
make clean              # Clean project
docker system prune -a  # Remove all unused Docker resources (careful!)
```

## Code Organization Principles

- **resources/**: API endpoints (use plural names, keep simple)
- **lib/**: Services, integrations, and shared business logic
- **models/**: Database models with business methods
- **types.py**: Pydantic models, enums (lowercase snake_case)
- **exc.py**: Custom exceptions
- **config.py**: Environment variables and settings
- **tasks/**: Background tasks and async processes

## Key Features Included

- **FastAPI**: Modern, async web framework
- **LangGraph**: For building LLM workflows
- **LangChain**: LLM integration ecosystem
- **Pydantic**: Data validation and settings
- **MongoDB**: Optional document database
- **uv**: Fast Python package management
- **Ruff**: Lightning-fast linting and formatting
- **pytest**: Comprehensive testing framework
- **Docker**: Containerization for development and production
- **Pre-commit**: Code quality enforcement

## Basic Application Files

### Main Application Entry Point

**File: `your_project_name/app.py`**
```python
from fastapi import FastAPI
from pydantic import BaseModel

from .config import config


app = FastAPI(
    title="Your Project Name",
    description="FastAPI + LangGraph application",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str
    message: str


class HelloResponse(BaseModel):
    message: str
    name: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        message="Service is running"
    )


@app.get("/hello/{name}", response_model=HelloResponse)
async def hello_world(name: str) -> HelloResponse:
    """Simple hello world endpoint"""
    return HelloResponse(
        message=f"Hello, {name}! Welcome to {config.app_name}",
        name=name
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {"message": "Welcome to Your Project Name API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=True
    )
```

### Configuration Management

**File: `your_project_name/config.py`**
```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="Your Project Name", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    env: str = Field(default="development", description="Environment")

    # API Keys (optional)
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")

    # Database (optional)
    mongodb_url: str | None = Field(
        default=None,
        description="MongoDB connection URL"
    )

# Global configuration instance
config = Config()
```

### Pydantic Models and Types

**File: `your_project_name/types.py`**
```python
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Environment(str, Enum):
    """Application environment types"""
    development = "development"
    staging = "staging"
    production = "production"


class LogLevel(str, Enum):
    """Logging levels"""
    debug = "DEBUG"
    info = "INFO"
    warning = "WARNING"
    error = "ERROR"
    critical = "CRITICAL"


class BaseResponse(BaseModel):
    """Base response model for API endpoints"""
    success: bool = Field(default=True, description="Request success status")
    message: str | None = Field(default=None, description="Response message")


class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = Field(default=False, description="Request success status")
    error_code: str | None = Field(default=None, description="Error code")
    details: dict[str, Any] | None = Field(default=None, description="Error details")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset from page and limit"""
        return (self.page - 1) * self.limit

```

### Custom Exceptions

**File: `your_project_name/exc.py`**
```python
from typing import Any


class BaseAppException(Exception):
    """Base exception for application-specific errors"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


```

### Package Initialization

**File: `your_project_name/__init__.py`**
```python
"""
Your Project Name

FastAPI + LangGraph application for [brief description]
"""

__version__ = "0.1.0"
__author__ = "Luis Fernando Garcia Cabrera"
__email__ = "fernando@hum-ascent.com"

from .app import app
from .config import config

__all__ = ["app", "config"]
```

## Testing the Basic Setup

After creating these files, test your basic application:

1. **Install dependencies**:
   ```bash
   make install
   ```

2. **Start the development server**:
   ```bash
   make dev
   # or manually:
   uv run uvicorn your_project_name.app:app --reload --host 0.0.0.0 --port 8080
   ```

3. **Test the endpoints**:
   ```bash
   # Health check
   curl http://localhost:8080/health

   # Hello world
   curl http://localhost:8080/hello/world

   # Root endpoint
   curl http://localhost:8080/

   # Interactive API docs
   open http://localhost:8080/docs
   ```

4. **Run code quality checks**:
   ```bash
   make format
   make lint
   ```

This setup provides a robust foundation for building LLM-powered applications with FastAPI and LangGraph.
