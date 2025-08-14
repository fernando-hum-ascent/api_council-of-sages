from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from loguru import logger

from ..models.conversations import get_active_conversation_or_create_one
from ..types import ChatUserEnum

if TYPE_CHECKING:
    from ..models.conversations import Conversation
from .graph_definition import orchestrator_graph
from .states import OrchestratorState


async def arun_agent(
    query: str, user_id: str, conversation_id: str | None = None
) -> dict[str, Any]:
    """
    Main function to execute the orchestrator graph with conversation
    persistence.

    Args:
        query: The user query to process
        user_id: Unique identifier for the user
        conversation_id: Optional conversation ID to continue existing
            conversation

    Returns:
        Dictionary containing:
        - final_response: The consolidated response
        - conversation_id: The conversation ID (existing or newly created)
        - agent_queries: Queries sent to each agent
        - agent_responses: Individual agent responses
    """
    conversation = None
    conversation_id_out = conversation_id
    try:
        # Get or create conversation
        conversation = await get_active_conversation_or_create_one(
            user_id, conversation_id
        )
        conversation_id_out = conversation.id

        # Get chat history from conversation
        chat_history = conversation.get_chat_history()

        # Build the initial state with conversation history
        state = build_orchestrator_state(
            query, user_id, conversation.id, chat_history
        )

        # Execute the graph with recursion limit
        result = await orchestrator_graph.ainvoke(
            state,  # type: ignore[arg-type]
            {"recursion_limit": 10},
        )

        # Extract and process the final response
        final_response = extract_final_response(result)

        # Save conversation messages
        await save_conversation_messages(conversation, query, final_response)

        # Build the output dictionary
        output = {
            "final_response": final_response,
            "conversation_id": conversation.id,
            "agent_queries": result.get("agent_queries", {}),
            "agent_responses": result.get("agent_responses", {}),
        }

        return output

    except Exception:  # noqa: BLE001
        # Log internally; return a generic message to the client
        logger.error(
            "Error executing orchestrator",
            extra={
                "action": "orchestrator_run",
                "user_id": user_id,
                "incoming_conversation_id": conversation_id,
                "conversation_id": conversation_id_out,
            },
        )
        return {
            "final_response": """Sorry,
            something went wrong while generating a response.""",
            "conversation_id": conversation_id_out,
            "agent_queries": {},
            "agent_responses": {},
        }


def build_orchestrator_state(
    query: str,
    user_id: str,
    conversation_id: str,
    chat_history: list[tuple[str, str]],
) -> OrchestratorState:
    """
    Build the initial state for the orchestrator graph with conversation
    history.

    Args:
        query: User query
        user_id: User identifier
        conversation_id: Conversation identifier
        chat_history: Previous conversation messages

    Returns:
        Initialized OrchestratorState
    """
    # Convert chat history to LangChain messages
    messages: list[BaseMessage] = []
    for role, content in chat_history:
        if role == "human":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    # Add current query as the latest human message
    messages.append(HumanMessage(content=query))

    state: OrchestratorState = {
        "messages": messages,
        "user_query": query,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "chat_history": chat_history,
        "agent_queries": {},
        "agent_responses": {},
        "final_response": None,
    }

    return state


async def save_conversation_messages(
    conversation: "Conversation", user_query: str, ai_response: str
) -> None:
    """
    Save the user query and AI response to the conversation.

    Args:
        conversation: The conversation object
        user_query: The user's query
        ai_response: The AI's response
    """
    # Add user message
    await conversation.add_message(user_query, ChatUserEnum.human)

    # Add AI response
    await conversation.add_message(ai_response, ChatUserEnum.ai)


def extract_final_response(result: dict[str, Any]) -> str:
    """
    Extract the final response from the graph result.

    Args:
        result: The graph execution result

    Returns:
        The final response string
    """
    # Try to get from final_response field first
    if result.get("final_response"):
        return result["final_response"]

    # Fallback: extract from last message
    messages = result.get("messages", [])
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, "content"):
            return last_message.content

    return "No response generated"
