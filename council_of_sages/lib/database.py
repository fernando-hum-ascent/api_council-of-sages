"""Database connection and initialization."""

from loguru import logger
from mongoengine import connect

from ..config import config


def init_database() -> None:
    """Initialize MongoDB connection."""
    if not config.mongodb_url:
        raise ValueError("MONGODB_URL environment variable is required")

    logger.info(f"Connecting to MongoDB: {config.mongodb_url}")

    try:
        connect(host=config.mongodb_url, uuidRepresentation="standard")
        logger.info("Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
