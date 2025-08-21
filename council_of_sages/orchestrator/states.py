from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from ..types import SageResponse


class OrchestratorState(TypedDict):
    """State for intelligent agent orchestration with conversation history"""

    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    user_id: str
    conversation_id: str
    turn_id: str  # Unique identifier for this interaction turn
    chat_history: list[tuple[str, str]]  # Previous conversation history
    agent_queries: dict[str, str]  # Specific queries for each agent
    agent_responses: dict[
        str, SageResponse
    ]  # Store structured sage responses only
    moderator_responses: dict[str, Any]  # Store moderator operation results
    final_response: str | None  # Final consolidated response
