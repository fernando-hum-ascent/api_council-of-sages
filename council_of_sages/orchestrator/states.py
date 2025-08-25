from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from ..types import SageResponse


class SageSpec(BaseModel):
    """Specification for a sage (predefined or dynamic)."""

    source: Literal["predefined", "dynamic"]
    key: str | None  # for predefined keys (e.g., "marcus_aurelius")
    name: str  # display/role name (for prompts)
    description: str  # short description to condition the role


class OrchestratorState(TypedDict):
    """State for intelligent agent orchestration with conversation history"""

    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    user_id: str
    conversation_id: str
    turn_id: str  # Unique identifier for this interaction turn
    chat_history: list[tuple[str, str]]  # Previous conversation history
    agent_queries: dict[str, str]  # Specific queries for each agent
    sages_to_run: list[SageSpec]  # Dynamic list of sages for a run
    agent_responses: dict[
        str, SageResponse
    ]  # Store structured sage responses only
    moderator_responses: dict[str, Any]  # Store moderator operation results
    final_response: str | None  # Final consolidated response
    max_sages_to_run: int  # Maximum number of sages to run
    cleaned_user_query: str | None  # Cleaned version of user_query for sages
