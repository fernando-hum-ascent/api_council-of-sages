from typing import Annotated, Any

from fastapi import Depends, status
from fastapi.routing import APIRouter

from ..lib.auth.dependencies import get_current_user_id
from ..orchestrator.llm_agent import arun_agent
from ..types import OrchestratorRequest, OrchestratorResponse

router = APIRouter(tags=["orchestrator"])

DESCRIPTION = (
    "Run the philosophical sage orchestrator with intelligent query "
    "distribution and conversation persistence. Requires Firebase "
    "authentication."
)

RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Invalid or missing authentication token",
        "content": {
            "application/json": {
                "example": {"detail": "Invalid authentication token"}
            }
        },
    },
    status.HTTP_402_PAYMENT_REQUIRED: {
        "description": "Insufficient balance for LLM requests",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Insufficient balance",
                    "balance": {
                        "balance_tenths_of_cents": -50,
                        "balance_usd": -0.05,
                        "updated_at": "2025-08-15T12:34:56Z",
                    },
                }
            }
        },
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Token expired or insufficient permissions",
        "content": {
            "application/json": {"example": {"detail": "Token has expired"}}
        },
    },
    status.HTTP_422_UNPROCESSABLE_ENTITY: {
        "description": "Invalid input data"
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Orchestrator execution failed"
    },
}


@router.post(
    "/orchestrator",
    status_code=status.HTTP_200_OK,
    response_model=OrchestratorResponse,
    responses=RESPONSES,
    description=DESCRIPTION,
    summary="Run Philosophical Sage Orchestrator",
)
async def run_orchestrator_endpoint(
    request: OrchestratorRequest,
    user_id: Annotated[
        str, Depends(get_current_user_id)
    ],  # Extract from token
) -> OrchestratorResponse:
    """
    Main endpoint to run the sage orchestrator with conversation persistence.

    **Authentication Required**: This endpoint requires a valid Firebase
    Bearer token in the Authorization header.

    This endpoint:
    1. Validates the Firebase Bearer token and extracts user_id
    2. Receives a user query and optional conversation_id
    3. Retrieves or creates conversation history from MongoDB
    4. Distributes the query intelligently to philosophical sages with
       conversation context
    5. Consolidates the wisdom into a coherent answer
    6. Saves the conversation to MongoDB
    7. Returns the final response with conversation details

    Args:
        request: Request containing query and optional conversation_id
        user_id: Automatically extracted from Firebase Bearer token

    Returns:
        OrchestratorResponse with sage wisdom and conversation details

    Raises:
        HTTPException: 401 for authentication failures, 500 for execution
        errors
    """

    return await arun_agent(
        query=request.query,
        user_id=user_id,  # Now comes from authenticated token
        conversation_id=request.conversation_id,
    )
