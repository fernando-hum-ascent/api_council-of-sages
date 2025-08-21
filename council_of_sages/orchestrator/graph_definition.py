import asyncio
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from loguru import logger

from ..types import SageResponse
from .moderator import ResponseModerator
from .states import OrchestratorState
from .tools.philosophical_sage import philosophical_sage


async def query_distribution_node(
    state: OrchestratorState,
) -> dict[str, Any]:
    """Moderator analyzes user query with conversation context and creates
    specific queries for each sage"""
    moderator = ResponseModerator()
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])

    # Get the full moderator response for tracking
    moderator_result = await moderator.distribute_query(
        user_query, chat_history
    )

    # Extract sage queries for the next node
    sage_queries = moderator_result["sage_queries"]

    return {
        "agent_queries": sage_queries,
        "moderator_responses": {"query_distribution": moderator_result},
    }


async def parallel_sages_node(
    state: OrchestratorState,
) -> dict[str, dict[str, SageResponse]]:
    """Execute selected sages in parallel with their specific queries and
    conversation context"""
    agent_queries = state["agent_queries"]

    # Prepare tasks only for sages that were selected by the moderator
    tasks = []
    sage_names = []

    # Dynamically iterate over agent_queries keys instead of hardcoded list
    for sage_name, query in agent_queries.items():
        tasks.append(
            philosophical_sage.ainvoke(
                {
                    "sage": sage_name,
                    "query": query,
                    "state": state,
                }
            )
        )
        sage_names.append(sage_name)

    # If no sages were selected, use fallback with one
    if not tasks:
        logger.error("No sages were selected, using fallback with one sage")
        user_query = state["user_query"]
        tasks = [
            philosophical_sage.ainvoke(
                {
                    "sage": "marcus_aurelius",
                    "query": f"From a Stoic perspective: {user_query}",
                    "state": state,
                }
            )
        ]
        sage_names = ["marcus_aurelius"]

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results for the selected sages
        sage_responses = {}

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Return structured error response
                sage_responses[sage_names[i]] = SageResponse(
                    answer=f"Error: {str(result)}",
                    summary="Error invoking sage.",
                )
            else:
                # result is already a SageResponse from the updated function
                sage_responses[sage_names[i]] = result  # type: ignore[assignment]

        return {"agent_responses": sage_responses}

    except Exception as e:  # noqa: BLE001
        return {
            "agent_responses": {
                "error": SageResponse(
                    answer=f"Failed to execute sages: {str(e)}",
                    summary="Error executing sages.",
                )
            }
        }


async def consolidation_node(
    state: OrchestratorState,
) -> dict[str, list | str | dict[str, Any]]:
    """Consolidate sage responses using the moderator with conversation
    context"""
    moderator = ResponseModerator()

    try:
        consolidated_response = await moderator.consolidate_responses(
            state["agent_responses"],
        )

        # Store consolidation result in moderator_responses
        consolidation_data = {
            "consolidated_response": consolidated_response,
            "input_sage_count": len(state["agent_responses"]),
            "sage_names": list(state["agent_responses"].keys()),
        }

        return {
            "messages": [HumanMessage(content=consolidated_response)],
            "final_response": consolidated_response,
            "moderator_responses": {
                **state.get("moderator_responses", {}),
                "consolidation": consolidation_data,
            },
        }

    except Exception as e:  # noqa: BLE001
        error_response = f"Error: {str(e)}"
        consolidation_error = {
            "consolidated_response": error_response,
            "error": str(e),
            "input_sage_count": len(state.get("agent_responses", {})),
        }

        return {
            "messages": [
                HumanMessage(
                    content=f"Error consolidating responses: {str(e)}"
                )
            ],
            "final_response": error_response,
            "moderator_responses": {
                **state.get("moderator_responses", {}),
                "consolidation": consolidation_error,
            },
        }


# Build the orchestrator graph
builder = StateGraph(OrchestratorState)

# Add nodes
builder.add_node("query_distribution", query_distribution_node)
builder.add_node("parallel_sages", parallel_sages_node)
builder.add_node("consolidation", consolidation_node)

# Set entry point
builder.set_entry_point("query_distribution")

# Add edges
builder.add_edge("query_distribution", "parallel_sages")
builder.add_edge("parallel_sages", "consolidation")
builder.add_edge("consolidation", END)

# Compile the graph
orchestrator_graph = builder.compile()
