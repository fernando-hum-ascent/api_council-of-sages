# Council of Sages Project Memory

## Project Overview
- **FastAPI + LangGraph** application for building intelligent AI workflows and multi-agent systems
- **Python 3.13+** required, uses modern tools (uv, ruff, pre-commit)
- **MongoDB** for data persistence
- **Docker** for containerization and local development

## Development Commands
- `make dev` - Start MongoDB + run FastAPI locally with auto-reload (recommended)
- `make test` - Run tests with coverage
- `make format` - Auto-format code with Ruff
- `make lint` - Run linting checks (Ruff + mypy)
- `make check-all` - Run all quality checks
- `make clean` - Stop services and clean up

## Code Structure & Conventions
- **`resources/`** - API endpoints (use plural names)
- **`lib/`** - Services, integrations, shared business logic
- **`models/`** - Database models with business methods
- **`types.py`** - Pydantic models, enums (snake_case)
- **`exc.py`** - Custom exceptions
- **`config.py`** - Environment variables and settings

## Development Principles
- Apply functional programming when possible
- Follow single responsibility principle
- Use descriptive names
- Reuse existing code before creating new
- Prefer libraries over custom implementations
- Follow style guide in ruff.toml

## Quality Checks & Code Standards
**CRITICAL: Follow .cursor/ rules strictly**

### Code Style & Formatting
- **PEP8** compliance with 79 character line limit
- **4 spaces** for indentation (no tabs)
- **Double quotes** for strings
- **snake_case** for functions/variables, **PascalCase** for classes
- **Type hints** required for all functions/methods
- Use **relative imports** (`from ..models.user import User`)
- Run `make format` (Ruff + Black) before committing

### Pydantic Models & Validation
- Use **Pydantic v2** for all input/output validation
- Prefer **native types** and `pydantic_extra_types` over custom validators
- **No custom validators** for cases already covered (coordinates, emails, URLs, dates)
- Enum properties must be **lowercase snake_case** matching their values
- **No redundant tests** for native Pydantic validation

### Python Code Requirements
- **Loguru** for all logging
- Avoid `except` without type or `except Exception`
- No `Any` type - be specific with types
- Clear docstrings for complex functions only
- **Functional programming** approach when possible
- **Single responsibility** principle

### Testing Standards
- Function names: `test_should_<result>_when_<condition>`
- Use **pytest.mark.parametrize** for multiple scenarios
- Follow **AAA pattern** (Arrange, Act, Assert)
- **VCR cassettes** for external HTTP requests
- **No tests** for native framework functionality
- High coverage on critical business logic

### Commands (run these before commits)
- `make format` - Auto-format with Ruff/Black
- `make lint` - Ruff + mypy checks
- `make test` - Run tests with coverage
- `make check-all` - Full validation suite
