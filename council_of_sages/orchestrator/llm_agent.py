import uuid
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from loguru import logger

from ..exc import PaymentRequiredError
from ..lib.billing.service import perform_pre_request_checks
from ..models.conversations import get_active_conversation_or_create_one
from ..models.messages import Message
from ..models.user import User
from ..types import ChatUserEnum, OrchestratorResponse, SageResponse

if TYPE_CHECKING:
    from ..models.conversations import Conversation
from fastapi import HTTPException, status

from .graph_definition import orchestrator_graph
from .states import OrchestratorState


async def arun_agent(
    query: str, user_id: str, conversation_id: str | None = None
) -> OrchestratorResponse:
    """
    Main function to execute the orchestrator graph with conversation
    persistence.

    Args:
        query: The user query to process
        user_id: Unique identifier for the user
        conversation_id: Optional conversation ID to continue existing
            conversation

    Returns:
        OrchestratorResponse with sage wisdom, conversation details, and
        billing information

    Raises:
        PaymentRequiredError: If user has insufficient balance
        RuntimeError: If billing information is not found in context
    """
    conversation = None
    conversation_id_out = conversation_id
    try:
        # Pre-request balance check - fail fast if insufficient funds
        await perform_pre_request_checks(user_id)

        # Get or create conversation
        conversation = await get_active_conversation_or_create_one(
            user_id, conversation_id
        )
        conversation_id_out = conversation.id

        # Generate turn_id for this interaction
        turn_id = str(uuid.uuid4())

        # Get chat history from conversation
        chat_history = await conversation.get_chat_history_with_summaries()

        # Build the initial state with conversation history
        state = build_orchestrator_state(
            query, user_id, conversation.id, chat_history, turn_id
        )

        # Execute the graph with recursion limit
        result = await orchestrator_graph.ainvoke(
            state,  # type: ignore[arg-type]
            {"recursion_limit": 10},
        )

        # Extract and process the final response
        final_response = extract_final_response(result)

        # Save conversation messages with turn_id and structured responses
        await save_conversation_messages(
            conversation, query, result.get("agent_responses", {}), turn_id
        )

        # Get current user balance from database (source of truth)
        current_balance = await User.get_current_balance(user_id)

        # Extract simplified agent responses (answers only)
        agent_responses_simplified = extract_answers_from_agent_responses(
            result.get("agent_responses", {})
        )

        # Return OrchestratorResponse directly
        return OrchestratorResponse(
            response=final_response,
            conversation_id=conversation.id,
            agent_queries=result.get("agent_queries", {}),
            agent_responses=agent_responses_simplified,
            moderator_responses=result.get("moderator_responses", {}),
            balance=current_balance,
        )
    except PaymentRequiredError as e:
        logger.warning(f"Payment required for user {user_id}: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=e.message,
        )
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
        return OrchestratorResponse(
            response="""Sorry,
            something went wrong while generating a response.""",
            conversation_id=conversation_id_out or "",
            agent_queries={},
            agent_responses={},
            moderator_responses=None,
            balance=None,
        )


def build_orchestrator_state(
    query: str,
    user_id: str,
    conversation_id: str,
    chat_history: list[tuple[str, str]],
    turn_id: str,
    max_sages_to_run: int = 5,
) -> OrchestratorState:
    """
    Build the initial state for the orchestrator graph with conversation
    history.

    Args:
        query: User query
        user_id: User identifier
        conversation_id: Conversation identifier
        chat_history: Previous conversation messages
        turn_id: Unique identifier for this interaction turn

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
        "turn_id": turn_id,
        "chat_history": chat_history,
        "sages_to_run": [],
        "agent_queries": {},
        "agent_responses": {},
        "moderator_responses": {},
        "final_response": None,
        "max_sages_to_run": max_sages_to_run,
        "cleaned_user_query": None,
    }

    return state


async def save_conversation_messages(
    conversation: "Conversation",
    user_query: str,
    agent_responses: dict[str, SageResponse],
    turn_id: str,
) -> None:
    """
    Save the user query and structured sage responses to standalone messages.

    Args:
        conversation: The conversation object
        user_query: The user's query
        agent_responses: Dictionary of sage responses
        turn_id: Unique identifier for this interaction turn
    """
    # Save user message with turn_id
    user_message = Message(
        conversation_id=conversation.id,
        role=ChatUserEnum.human,
        content=user_query,
        turn_id=turn_id,
    )
    await user_message.async_save()

    # Save one AI message per sage with structured content
    for sage_name, sage_response in agent_responses.items():
        # Convert SageResponse to dict if it's a Pydantic model
        if hasattr(sage_response, "model_dump"):
            response_dict = sage_response.model_dump()
        else:
            response_dict = sage_response  # type: ignore[assignment]

        ai_message = Message(
            conversation_id=conversation.id,
            role=ChatUserEnum.ai,
            content=response_dict["answer"],
            summary=response_dict["summary"],
            turn_id=turn_id,
            sage=sage_name,
        )
        await ai_message.async_save()


def extract_answers_from_agent_responses(
    agent_responses: dict[str, SageResponse],
) -> dict[str, str]:
    """
    Extract only the answers from the agent responses dictionary.

    Args:
        agent_responses: Dictionary of sage responses with full SageResponse
            objects

    Returns:
        Dictionary with sage names as keys and only their answers as values
    """
    answers = {}
    for sage_name, sage_response in agent_responses.items():
        # Handle both Pydantic model and dict cases
        if hasattr(sage_response, "answer"):
            answers[sage_name] = sage_response.answer
        elif isinstance(sage_response, dict):
            answers[sage_name] = sage_response.get("answer", "")
        else:
            answers[sage_name] = ""
    return answers


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
