import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from .config import config
from .lib.database import init_database
from .resources.orchestrator import router as orchestrator_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Council of Sages API...")
    try:
        await asyncio.to_thread(init_database)
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database during startup: {e}")
        raise

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Council of Sages API...")


app = FastAPI(
    title="Council of Sages",
    description="FastAPI + LangGraph application",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=config.cors_allow_credentials,
    allow_methods=config.cors_allow_methods,
    allow_headers=config.cors_allow_headers,
)

# Include routers
app.include_router(orchestrator_router)


class HealthResponse(BaseModel):
    status: str
    message: str


class HelloResponse(BaseModel):
    message: str
    name: str


@app.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint"""
    return HealthResponse(status="healthy", message="Service is running")


@app.get("/hello/{name}")
async def hello_world(name: str) -> HelloResponse:
    """Simple hello world endpoint"""
    return HelloResponse(
        message=f"Hello, {name}! Welcome to {config.app_name}", name=name
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint"""
    return {"message": "Welcome to Council of Sages API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080, reload=True)
