# Render CI/CD Deployment Best Practices (Custom for Council of Sages)

This guide defines a practical, reliable CI/CD workflow to develop locally and deploy automatically to two environments on Render: development and production.

- Tech: FastAPI, Docker (multi-stage), uv, MongoDB (Atlas), Firebase Auth
- Service: Docker Web Service on Render
- Ports: app listens on `$PORT` (Render sets it); health check at `/health`


## Environment Strategy

- Branches
  - `feature/*`: local development, open PRs into `dev`
  - `dev`: auto-deploys to Render Dev
  - `main`: auto-deploys to Render Prod (after PR review)
- Environments
  - Dev service: lower cost instance, permissive CORS, debug off but verbose logs OK
  - Prod service: higher availability, stricter CORS, autoscaling as needed


## Render Services (Docker)

Create two Docker-based Web Services from the same repo and Dockerfile.

- Service names
  - `council-of-sages-api-dev` (from `dev`)
  - `council-of-sages-api` (from `main`)
- Region: same region as your DB (recommended)
- Instance type: start with XS or S for Dev; S or M for Prod, scale as needed
- Auto deploy: enabled on successful CI
- Health check path: `/health`
- Start command (override the Dockerfile CMD to use `$PORT` and bind to 0.0.0.0):
  - `uv run uvicorn council_of_sages.app:app --host 0.0.0.0 --port $PORT`
- Docker context: repo root; Dockerfile: `Dockerfile`
- If you prefer, add `EXPOSE 8080` to the Dockerfile and still use `$PORT` at runtime

Why override CMD? The current `python -m council_of_sages.app` runs uvicorn with port 8080; Render expects listening on `$PORT`.


## Environment Variables (Render)

Set these in each Render service (use Environment Groups to share across services, with per-service overrides for CORS and URLs):

- Application
  - `ENV`: `development` (Dev) / `production` (Prod)
  - `DEBUG`: `false`
  - `LOG_LEVEL`: `INFO` (Dev can use `DEBUG` during troubleshooting)
  - `CORS_ORIGINS`: JSON list of allowed origins, e.g. `["http://localhost:3000", "https://dev.yourapp.com"]` for Dev, `["https://yourapp.com"]` for Prod
- Database
  - `MONGODB_URL`: MongoDB Atlas connection string for each env (separate DBs)
- LLM providers (optional)
  - `OPENAI_API_KEY`: set if used
  - `ANTHROPIC_API_KEY`: set if used
- Firebase (required)
  - `FIREBASE_PROJECT_ID`: your Firebase project ID
  - `FIREBASE_SERVICE_ACCOUNT_KEY`: service account JSON as a single-line string

Notes:
- All variables are defined/validated via `council_of_sages/config.py` (Pydantic Settings)
- Lists (e.g., `CORS_ORIGINS`) can be set as JSON strings; Pydantic will parse them
- Do not commit secrets. Use Render Environment Groups and per-service overrides


## Database Strategy

- Use MongoDB Atlas for both Dev and Prod (Render does not provide managed MongoDB)
- Create two databases or two clusters: `council_of_sages_dev` and `council_of_sages`
- Create separate DB users with least privileges per env
- Put each env’s connection string in the corresponding Render service


## CI with GitHub Actions

Use CI to block deployments on failing tests/linters. Render will auto-deploy only after the branch builds green.

Place this in `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main, dev ]

jobs:
  build-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up UV
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Install deps
        run: |
          uv venv --python 3.13
          uv pip install -e ".[dev,linting,testing]"

      - name: Lint & Typecheck
        run: |
          uv run ruff format --check .
          uv run ruff check .
          uv run mypy council_of_sages tests scripts

      - name: Run tests
        env:
          # Minimal env so config loads; set dummy values for tests if needed
          FIREBASE_PROJECT_ID: dummy
          FIREBASE_SERVICE_ACCOUNT_KEY: '{"type":"service_account","project_id":"dummy"}'
        run: |
          uv run pytest -q
```

Branch protections:
- Require the CI workflow to pass before merging to `dev`/`main`
- Require PR reviews for `main`


## Render Deploy Flow

1) Developer workflow
- Work on `feature/*` locally using `make dev`
- Open PR to `dev` → CI runs → upon merge, Render Dev auto-deploys
- Open PR from `dev` to `main` → CI runs → upon merge, Render Prod auto-deploys

2) Render configuration per service
- Connect repo, select branch filter: `dev` for Dev, `main` for Prod
- Set Start Command to: `uv run uvicorn council_of_sages.app:app --host 0.0.0.0 --port $PORT`
- Set Health Check Path: `/health`
- Configure environment variables (or attach Environment Group)
- Enable auto-deploy on commit

3) Rollbacks
- Use Render’s Deploys tab → select a previous successful build → Rollback
- Keep images immutable by using multi-stage Docker builds (already configured)


## Optional: Infrastructure as Code (render.yaml)

For reproducible setup, add `render.yaml` in the repo root to define both services. Example:

```yaml
services:
  - type: web
    name: council-of-sages-api-dev
    env: docker
    plan: starter
    branch: dev
    healthCheckPath: /health
    dockerfilePath: ./Dockerfile
    dockerContext: .
    autoDeploy: true
    startCommand: uv run uvicorn council_of_sages.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ENV
        value: development
      - key: DEBUG
        value: "false"
      - key: LOG_LEVEL
        value: INFO
      - key: CORS_ORIGINS
        value: '["http://localhost:3000"]'
      - key: MONGODB_URL
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: FIREBASE_PROJECT_ID
        sync: false
      - key: FIREBASE_SERVICE_ACCOUNT_KEY
        sync: false

  - type: web
    name: council-of-sages-api
    env: docker
    plan: standard
    branch: main
    healthCheckPath: /health
    dockerfilePath: ./Dockerfile
    dockerContext: .
    autoDeploy: true
    startCommand: uv run uvicorn council_of_sages.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: ENV
        value: production
      - key: DEBUG
        value: "false"
      - key: LOG_LEVEL
        value: INFO
      - key: CORS_ORIGINS
        value: '["https://your-frontend-domain"]'
      - key: MONGODB_URL
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: FIREBASE_PROJECT_ID
        sync: false
      - key: FIREBASE_SERVICE_ACCOUNT_KEY
        sync: false
```

Notes:
- `sync: false` tells Render to manage values in the dashboard (or via env groups) rather than in git
- Adjust `plan` per instance size. Consider autoscaling for production


## Local ↔ Render Parity

- Local dev uses `docker-compose.yaml` to start MongoDB; in Render use Atlas
- Health check path `/health` works locally and on Render
- Use the same env keys locally (`.env`) and in Render services
- Prefer the same Python version (3.13) and the same uv-based installation flow


## Operational Best Practices

- Logging: keep `LOG_LEVEL=INFO` in Prod; prefer structured logs if adding log processors later
- Monitoring: use Render Metrics and Alerts for error rate/latency. Consider external APM if needed
- Security:
  - Never commit secrets; use Render secrets or environment groups
  - Restrict CORS to known origins in Prod
  - Use dedicated least-privileged DB users per env
- Performance:
  - Scale instance size/replicas based on P95 latency and CPU
  - Add HTTP keep-alive and gzip (Uvicorn/Starlette defaults are reasonable)
- Backups/DR: enable backups on MongoDB Atlas; document restore runbooks


## Quick Checklist

- Dev service on `dev`, Prod on `main`
- Start Command binds to `0.0.0.0` and `$PORT`
- Health check at `/health`
- Separate secrets per environment
- CI blocks merges on failing lint/tests
- Rollback strategy tested on Render
