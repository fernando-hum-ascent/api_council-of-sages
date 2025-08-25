import asyncio
from typing import Any, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from loguru import logger

from ..lib.billing.billing_llm_proxy import BillingLLMProxy
from ..types import SageResponse
from .moderator import ResponseModerator
from .prompt_modules import USER_INPUT_CLEANER_PROMPT
from .states import OrchestratorState, SageSpec
from .tools.philosophical_sage import execute_sage_spec


async def sage_selection_node(
    state: OrchestratorState,
) -> dict[str, Any]:
    """Moderator selects relevant sages (predefined and dynamic) for the user
    query"""
    moderator = ResponseModerator()
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])

    # Get sage selection from moderator
    sage_specs = await moderator.select_sages(user_query, chat_history)

    return {
        "sages_to_run": sage_specs,
        "moderator_responses": {
            "sage_selection": {"sage_count": len(sage_specs)}
        },
    }


async def clean_user_input_node(state: OrchestratorState) -> dict[str, Any]:
    """Rewrite the user query removing explicit requests to include names of
    sages/personas/people. Return only the cleaned question.

    Example:
      In:  "Should I try to beat the market? Please include Charlie Munger"
      Out: "Should I try to beat the market?"
    """
    user_query = state["user_query"]

    # LLM from prompt module + billing
    raw_llm = ChatAnthropic(
        model=USER_INPUT_CLEANER_PROMPT.model,
        temperature=USER_INPUT_CLEANER_PROMPT.temperature,
    )
    llm = BillingLLMProxy(raw_llm)

    formatted_prompt = USER_INPUT_CLEANER_PROMPT.template.format(
        user_query=user_query
    )

    try:
        response = await llm.ainvoke(formatted_prompt)
        cleaned = str(getattr(response, "content", "")).strip()
        cleaned = cleaned.strip().rstrip('"')

        return {
            "cleaned_user_query": cleaned if cleaned else user_query,
        }
    except Exception:  # noqa: BLE001
        # Fail open by returning original query
        return {
            "cleaned_user_query": user_query,
        }


def limit_sages_to_run(
    sages_to_run: list[SageSpec], state: OrchestratorState
) -> list[SageSpec]:
    """Limit the number of sages to run, defaulting to 5.

    Allows override via `max_sages_to_run` in the state.
    """
    max_sages_to_run = state.get("max_sages_to_run", 5)
    if isinstance(max_sages_to_run, int) and max_sages_to_run > 0:
        limited_sages_to_run = sages_to_run[:max_sages_to_run]
        if len(sages_to_run) > len(limited_sages_to_run):
            logger.info(
                "Limiting sages to run: {} requested, {} will execute",
                len(sages_to_run),
                len(limited_sages_to_run),
            )
        return limited_sages_to_run
    return sages_to_run


async def parallel_sages_node(
    state: OrchestratorState,
) -> dict[str, dict[str, SageResponse]]:
    """Execute selected sages in parallel using SageSpec"""
    sages_to_run = limit_sages_to_run(state.get("sages_to_run", []), state)
    user_query = cast(
        str, state.get("cleaned_user_query") or state["user_query"]
    )  # prefer cleaned
    chat_history = state.get("chat_history", [])
    # Prepare tasks for all selected sages
    tasks = []
    sage_names = []

    for sage_spec in sages_to_run:
        tasks.append(execute_sage_spec(sage_spec, user_query, chat_history))
        sage_names.append(sage_spec.name)

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
                # result is already a SageResponse from execute_sage_spec
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
builder.add_node("sage_selection", sage_selection_node)
builder.add_node("clean_user_input", clean_user_input_node)
builder.add_node("parallel_sages", parallel_sages_node)
builder.add_node("consolidation", consolidation_node)

# Fork at START so both nodes run concurrently
builder.add_edge(START, "sage_selection")
builder.add_edge(START, "clean_user_input")

# Join before parallel_sages (it will await both parents)
builder.add_edge("sage_selection", "parallel_sages")
builder.add_edge("clean_user_input", "parallel_sages")

# Then consolidation and END
builder.add_edge("parallel_sages", "consolidation")
builder.add_edge("consolidation", END)

# Compile the graph
orchestrator_graph = builder.compile()
