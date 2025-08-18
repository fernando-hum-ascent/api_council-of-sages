# flake8: noqa: E402
from dotenv import load_dotenv

load_dotenv()

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from .config import config
from .lib.auth.dependencies import get_current_user_id, set_firebase_auth
from .lib.auth.firebase_auth import FirebaseAuth
from .lib.database import init_database
from .resources.orchestrator import router as orchestrator_router
from .resources.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Council of Sages API...")
    try:
        # Initialize Firebase Authentication
        logger.info("Initializing Firebase authentication...")
        firebase_auth = FirebaseAuth(
            project_id=config.firebase_project_id,
            service_account_key=config.firebase_service_account_key,
        )
        set_firebase_auth(firebase_auth)
        logger.info("Firebase authentication initialized successfully")

        # Initialize Database
        await asyncio.to_thread(init_database)
        logger.info("Database initialization completed successfully")

    except Exception as e:
        logger.error(f"Failed to initialize services during startup: {e}")
        raise

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Council of Sages API...")


app = FastAPI(
    title="Council of Sages",
    description="FastAPI + LangGraph application with Firebase Authentication",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS with explicit Authorization header support
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=config.cors_allow_credentials,
    allow_methods=config.cors_allow_methods,
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",  # Explicitly allow Authorization header for tokens
    ],
)

# Include routers
app.include_router(orchestrator_router)
app.include_router(users_router)


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


@app.get("/health/authenticated")
async def authenticated_health(
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> HealthResponse:
    """Authenticated health check endpoint to test Firebase auth"""
    return HealthResponse(
        status="healthy",
        message=f"Authenticated service is running for user: {user_id}",
    )


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

    port_value = os.getenv("PORT", "8080")
    try:
        port = int(port_value)
    except ValueError:
        logger.warning(
            f"Invalid PORT value '{port_value}', defaulting to 8080"
        )
        port = 8080

    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104
