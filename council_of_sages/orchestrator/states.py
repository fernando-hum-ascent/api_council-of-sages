from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class OrchestratorState(TypedDict):
    """State for intelligent agent orchestration with conversation history"""

    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    user_id: str
    conversation_id: str
    chat_history: list[tuple[str, str]]  # Previous conversation history
    agent_queries: dict[str, str]  # Specific queries for each agent
    agent_responses: dict[str, str]  # Store individual agent responses
    final_response: str | None  # Final consolidated response
