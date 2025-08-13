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
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    cp /root/.local/bin/uvx /usr/local/bin/uvx || true

# Clean up curl
RUN apt-get purge -y --auto-remove curl

# Development image
FROM base as development
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY council_of_sages council_of_sages/
RUN uv pip install --system -e ".[dev,linting,testing]"
COPY . .

# Production image
FROM base as production
COPY pyproject.toml ./
COPY council_of_sages council_of_sages/
RUN uv pip install --system .

# Create non-root user
RUN useradd -m -u 1000 app \
    && chown -R app:app /app
USER app

# Command to run the application (override for platforms like Railway/Render)
# Use shell form to allow $PORT expansion with a default of 8080
CMD uv run uvicorn council_of_sages.app:app --host 0.0.0.0 --port ${PORT:-8080}
