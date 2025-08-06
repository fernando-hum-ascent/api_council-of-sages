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
    details: dict[str, Any] | None = Field(
        default=None, description="Error details"
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""

    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset from page and limit"""
        return (self.page - 1) * self.limit
