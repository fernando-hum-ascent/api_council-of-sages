from datetime import datetime
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


class ChatUserEnum(str, Enum):
    """Enum for chat user roles"""

    human = "human"
    ai = "ai"


class SageEnum(str, Enum):
    """Enum for available philosophical sages"""

    marcus_aurelius = "marcus_aurelius"
    nassim_taleb = "nassim_taleb"
    naval_ravikant = "naval_ravikant"


class SageResponse(BaseModel):
    """Structured response from a philosophical sage"""

    answer: str = Field(description="Detailed response from the sage")
    summary: str = Field(description="Concise summary for future context")


class OrchestratorRequest(BaseModel):
    """Request model for orchestrator endpoint with conversation support"""

    query: str = Field(description="User query to process")
    # Remove user_id field - will be extracted from Bearer token
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Optional conversation ID to continue existing conversation"
        ),
    )


class Balance(BaseModel):
    """User balance information"""

    balance_tenths_of_cents: int = Field(
        description="Balance in integer tenths of cents"
    )
    balance_usd: float = Field(description="Balance in USD (derived)")
    updated_at: datetime = Field(description="Last update timestamp")


class OrchestratorResponse(BaseModel):
    """Response model for orchestrator endpoint"""

    response: str = Field(description="The consolidated response")
    conversation_id: str = Field(description="ID of the conversation")
    agent_queries: dict[str, str] = Field(
        description="Queries sent to each agent"
    )
    agent_responses: dict[str, str] = Field(
        description="Individual agent answers (simplified responses)"
    )
    moderator_responses: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Moderator operation results (query distribution, consolidation)"
        ),
    )
    balance: Balance | None = Field(
        default=None, description="User balance information if available"
    )


class BillingInfo(BaseModel):
    """Billing information for an LLM request"""

    model_name: str = Field(description="Name of the model used")
    input_tokens: int = Field(description="Number of input tokens")
    output_tokens: int = Field(description="Number of output tokens")
    cost_tenths_of_cents: int = Field(
        description="Cost in integer tenths of cents"
    )
    balance: Balance = Field(description="Updated user balance")
