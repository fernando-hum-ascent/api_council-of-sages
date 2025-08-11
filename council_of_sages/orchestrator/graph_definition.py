import asyncio

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from loguru import logger

from .moderator import ResponseModerator
from .states import OrchestratorState
from .tools.philosophical_sage import philosophical_sage


async def query_distribution_node(
    state: OrchestratorState,
) -> dict[str, dict[str, str]]:
    """Moderator analyzes user query with conversation context and creates
    specific queries for each sage"""
    moderator = ResponseModerator()
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])

    try:
        sage_queries = await moderator.distribute_query(
            user_query, chat_history
        )
        return {"agent_queries": sage_queries}

    except Exception as e:  # noqa: BLE001
        # Fallback queries if distribution fails
        context_note = " (with conversation context)" if chat_history else ""
        fallback_queries = {
            "marcus_aurelius": (
                f"From a Stoic perspective{context_note}: {user_query}"
            ),
            "nassim_taleb": (
                f"From an antifragile perspective{context_note}: {user_query}"
            ),
            "naval_ravikant": (
                f"From an entrepreneurial philosophy perspective"
                f"{context_note}: {user_query}"
            ),
            "distribution_rationale": (
                f"Fallback distribution due to error: {str(e)}"
            ),
        }
        return {"agent_queries": fallback_queries}


async def parallel_sages_node(
    state: OrchestratorState,
) -> dict[str, dict[str, str]]:
    """Execute selected sages in parallel with their specific queries and
    conversation context"""
    agent_queries = state["agent_queries"]

    # Define available sages
    available_sages = ["marcus_aurelius", "nassim_taleb", "naval_ravikant"]

    # Prepare tasks only for sages that were selected by the moderator
    tasks = []
    sage_names = []

    # Check which sages have queries and create tasks accordingly
    for sage in available_sages:
        if sage in agent_queries:
            tasks.append(
                philosophical_sage.ainvoke(
                    {
                        "sage": sage,
                        "query": agent_queries[sage],
                        "state": state,
                    }
                )
            )
            sage_names.append(sage)

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
                sage_responses[sage_names[i]] = f"Error: {str(result)}"
            else:
                sage_responses[sage_names[i]] = str(result)

        return {"agent_responses": sage_responses}

    except Exception as e:  # noqa: BLE001
        return {
            "agent_responses": {"error": f"Failed to execute sages: {str(e)}"}
        }


async def consolidation_node(
    state: OrchestratorState,
) -> dict[str, list | str]:
    """Consolidate sage responses using the moderator with conversation
    context"""
    moderator = ResponseModerator()
    chat_history = state.get("chat_history", [])

    try:
        consolidated_response = await moderator.consolidate_responses(
            state["user_query"],
            state["agent_queries"],
            state["agent_responses"],
            chat_history,
        )

        return {
            "messages": [HumanMessage(content=consolidated_response)],
            "final_response": consolidated_response,
        }

    except Exception as e:  # noqa: BLE001
        return {
            "messages": [
                HumanMessage(
                    content=f"Error consolidating responses: {str(e)}"
                )
            ],
            "final_response": f"Error: {str(e)}",
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
