# Council of Sages

FastAPI + LangGraph application for building intelligent AI workflows and multi-agent systems.

## 🚀 Quick Start

```bash
# Clone and navigate to project
cd api_council-of-sages

# Check system dependencies
make check-deps

# Install dependencies and setup environment
make install

# Create environment file
cp .env.example .env
# Edit .env with your actual API keys

# Start development server
make dev
```

Your API will be available at:
- **API**: http://localhost:8080
- **Interactive Docs**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## 🛠 System Requirements

### Required Tools
- **Python 3.13+**: Use pyenv for version management
- **uv**: Modern Python package manager and environment tool
- **Docker**: For containerization and local services
- **Docker Compose**: For multi-service local development
- **pre-commit**: For git hooks and code quality

### Installation Commands

**macOS (with Homebrew):**
```bash
brew install uv pre-commit docker
```

**Linux/macOS (manual):**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install pre-commit
pip install pre-commit
```

## 📁 Project Structure

```
council-of-sages/
├── pyproject.toml           # Python project configuration
├── Makefile                # Development commands
├── Dockerfile              # Container configuration
├── docker-compose.yaml     # Local development services
├── .python-version         # Python version specification
├── ruff.toml               # Code formatting and linting
├── .pre-commit-config.yaml # Git hooks configuration
├── .env.example            # Environment variables template
├── council_of_sages/       # Main application package
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

## 🔧 Development Setup

### 1. Initial Setup

```bash
# Check system dependencies
make check-deps

# Install dependencies and pre-commit hooks
make install

# Create environment file from template
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your API keys and settings:

```env
# Application
DEBUG=true
LOG_LEVEL=DEBUG
ENV=development

# API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Database
MONGODB_URL=mongodb://root:example@localhost:27017/council_of_sages?authSource=admin
```

### 3. Test Setup

```bash
# Format and check code
make format
make lint

# Run tests
make test
```

## 🏃‍♂️ Development Workflow

### Option 1: Local Development (Recommended)

Run your FastAPI app locally with Docker services:

```bash
# Start MongoDB and run FastAPI locally with auto-reload
make dev

# Check running services
make ps

# View database logs
docker compose logs mongodb

# Stop services when done
make down
```

### Option 2: Full Docker Development

Run everything in Docker containers:

```bash
# Build Docker images
make build

# Start all services (app + MongoDB)
make up

# View logs from all services
make logs

# Access the app container
make shell

# Stop everything
make down
```

## 📝 Available Commands

### Development Commands
```bash
make dev          # Start MongoDB + run FastAPI locally with auto-reload
make run          # Run the service without auto-reload
make ps           # List running Docker services
make logs         # View logs from all services
make shell        # Open shell in the running app container
```

### Code Quality Commands
```bash
make format       # Auto-format code with Ruff
make lint         # Run linting checks (Ruff + mypy)
make test         # Run tests with coverage
make spellcheck   # Check spelling with codespell
make check-all    # Run all quality checks
```

### Docker Commands
```bash
make build        # Build Docker images
make build-prod   # Build production Docker image
make up           # Start all services
make down         # Stop all services
make db           # Start only MongoDB
```

### Cleanup Commands
```bash
make clean        # Stop services and clean up caches/volumes
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
make test

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_specific.py

# Run with coverage report
uv run pytest --cov=council_of_sages --cov-report=html
```

## 🐳 Docker Services

The project includes these Docker services:

### MongoDB
- **Port**: 27017
- **Username**: root
- **Password**: example
- **Connection**: `mongodb://root:example@localhost:27017/council_of_sages?authSource=admin`
- **Data**: Persisted in `mongodb_data` volume

### App (when using Docker)
- **Port**: 8080
- **Auto-reload**: Enabled in development mode
- **Volumes**: Source code mounted for live updates


## 🏗 Code Organization

- **`resources/`**: API endpoints (use plural names, keep simple)
- **`lib/`**: Services, integrations, and shared business logic
- **`models/`**: Database models with business methods
- **`types.py`**: Pydantic models, enums (lowercase snake_case)
- **`exc.py`**: Custom exceptions
- **`config.py`**: Environment variables and settings
- **`tasks/`**: Background tasks and async processes

## 🎯 Development Principles

- Apply **functional programming** when possible
- Follow **single responsibility principle**
- Use **descriptive names** for variables, functions, and classes
- **Reuse existing code** before creating new functions
- **Prefer libraries** over custom implementations
- Follow the **style guide** defined in `ruff.toml`

## 🔧 Troubleshooting

### Port Conflicts
```bash
# Check what's using port 8080 or 27017
lsof -i :8080
lsof -i :27017

# Change ports in docker-compose.yaml if needed
```

### Docker Issues
```bash
# Reset Docker environment
make clean
docker system prune -a  # Remove all unused Docker resources

# Check Docker service status
docker compose ps
docker compose logs mongodb
```

### Database Connection
```bash
# Test MongoDB connection
docker compose exec mongodb mongosh mongodb://root:example@localhost:27017/admin

# Connect from host
mongosh "mongodb://root:example@localhost:27017/council_of_sages?authSource=admin"
```

### Python Environment
```bash
# Recreate virtual environment
make clean
make install

# Check Python version
python --version  # Should be 3.13+
```

## 🚀 Production Deployment

Build and run the production image:

```bash
# Build production image
make build-prod

# Run production container
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your_key \
  -e MONGODB_URL=your_mongo_url \
  council-of-sages:latest
```

## 📚 Technology Stack

- **[FastAPI](https://fastapi.tiangolo.com/)**: Modern, async web framework
- **[LangGraph](https://langchain-ai.github.io/langgraph/)**: For building LLM workflows
- **[LangChain](https://langchain.readthedocs.io/)**: LLM integration ecosystem
- **[Pydantic](https://pydantic.dev/)**: Data validation and settings
- **[MongoDB](https://www.mongodb.com/)**: Document database (optional)
- **[uv](https://docs.astral.sh/uv/)**: Fast Python package management
- **[Ruff](https://docs.astral.sh/ruff/)**: Lightning-fast linting and formatting
- **[pytest](https://pytest.org/)**: Comprehensive testing framework

## 📄 License

[Add your license information here]

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make check-all` to ensure code quality
5. Submit a pull request

---

**Happy coding! 🚀**
