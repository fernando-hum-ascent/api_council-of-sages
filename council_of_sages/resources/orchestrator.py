from typing import Any

from fastapi import HTTPException, status
from fastapi.routing import APIRouter

from ..orchestrator.llm_agent import arun_agent
from ..types import OrchestratorRequest, OrchestratorResponse

router = APIRouter(tags=["orchestrator"])

DESCRIPTION = (
    "Run the philosophical sage orchestrator with intelligent query "
    "distribution and conversation persistence"
)
RESPONSES: dict[int | str, dict[str, Any]] = {
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
)
async def run_orchestrator_endpoint(
    request: OrchestratorRequest,
) -> OrchestratorResponse:
    """
    Main endpoint to run the sage orchestrator with conversation persistence.

    This endpoint:
    1. Receives a user query, user_id, and optional conversation_id
    2. Retrieves or creates conversation history from MongoDB
    3. Distributes the query intelligently to philosophical sages with
       conversation context
    4. Consolidates the wisdom into a coherent answer
    5. Saves the conversation to MongoDB
    6. Returns the final response with conversation details
    """
    try:
        # Call the orchestrator sage function with conversation support
        result = await arun_agent(
            query=request.query,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
        )

        return OrchestratorResponse(
            response=result["final_response"],
            conversation_id=result["conversation_id"],
            agent_queries=result["agent_queries"],
            agent_responses=result["agent_responses"],
        )

    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sage orchestrator execution failed: {str(e)}",
        )
