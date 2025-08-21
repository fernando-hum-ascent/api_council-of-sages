from typing import Annotated

from langchain_anthropic import ChatAnthropic

# Temporarily disabled Pydantic parsing due to parsing issues
# from langchain_core.output_parsers import PydanticOutputParser  # noqa: ERA001,E501
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import InjectedState
from loguru import logger
from pydantic import BaseModel, Field

from ...lib.billing.billing_llm_proxy import BillingLLMProxy
from ...types import SageEnum, SageResponse
from ..prompt_modules import (
    # MARCUS_AURELIUS_PARSER,
    MARCUS_AURELIUS_PROMPT,
    # NASSIM_TALEB_PARSER,
    NASSIM_TALEB_PROMPT,
    # NAVAL_RAVIKANT_PARSER,
    NAVAL_RAVIKANT_PROMPT,
)
from ..states import OrchestratorState


class PhilosophicalSageInput(BaseModel):
    """Input model for the unified philosophical sage tool"""

    sage: SageEnum = Field(description="Which philosophical sage to consult")
    query: str = Field(description="Query for the sage")
    state: Annotated[OrchestratorState | None, InjectedState]


# Pre-constructed and wrapped LLM instances (singleton pattern for billing)
_SAGE_LLMS = {}


def _get_sage_llm(sage: SageEnum) -> BillingLLMProxy:
    """Get or create a billing-wrapped LLM for the sage (singleton pattern)"""
    if sage not in _SAGE_LLMS:
        sage_configs = {
            SageEnum.marcus_aurelius: MARCUS_AURELIUS_PROMPT,
            SageEnum.nassim_taleb: NASSIM_TALEB_PROMPT,
            SageEnum.naval_ravikant: NAVAL_RAVIKANT_PROMPT,
        }

        prompt_model = sage_configs[sage]
        raw_llm = ChatAnthropic(
            model=prompt_model.model,
            temperature=prompt_model.temperature,
        )
        _SAGE_LLMS[sage] = BillingLLMProxy(raw_llm)

    return _SAGE_LLMS[sage]


# Sage configurations with their specific settings
# (parsers temporarily disabled)  # ruff: noqa: ERA001
SAGE_CONFIGS = {
    SageEnum.marcus_aurelius: {
        "prompt": MARCUS_AURELIUS_PROMPT,
        # "parser": MARCUS_AURELIUS_PARSER,  # noqa: ERA001
    },
    SageEnum.nassim_taleb: {
        "prompt": NASSIM_TALEB_PROMPT,
        # "parser": NASSIM_TALEB_PARSER,  # noqa: ERA001
    },
    SageEnum.naval_ravikant: {
        "prompt": NAVAL_RAVIKANT_PROMPT,
        # "parser": NAVAL_RAVIKANT_PARSER,  # noqa: ERA001
    },
}


async def philosophical_sage_function(
    sage: SageEnum, query: str, state: OrchestratorState
) -> SageResponse:
    """Unified sage function that provides wisdom based on the specified
    sage parameter"""

    # Get sage-specific configuration
    config = SAGE_CONFIGS[sage]
    prompt_model = config["prompt"]
    # parser temporarily disabled  # ruff: noqa: ERA001
    # parser: PydanticOutputParser = config["parser"]

    # Get the pre-wrapped LLM instance
    llm = _get_sage_llm(sage)

    # Type assertion for mypy
    assert hasattr(prompt_model, "template")

    # Extract chat history from injected state
    chat_history = state.get("chat_history", [])

    # Format chat history for context
    if chat_history:
        chat_context = "\\n".join(
            [f"{role.upper()}: {content}" for role, content in chat_history]
        )
    else:
        chat_context = "No previous conversation context."

    # Get original user query from state
    original_user_query = state.get("user_query", query)

    # Format the prompt without format instructions (plain text response)
    formatted_prompt = prompt_model.template.format(
        original_user_query=original_user_query,
        query=query,
        chat_context=chat_context,
    )

    try:
        # Invoke the LLM
        response = await llm.ainvoke(formatted_prompt)

        # Get plain text response
        plain_response = str(response.content).strip()

        # Hardcode the desired output format with the plain response
        sage_response = SageResponse(
            answer=plain_response,
            summary=plain_response,  # Use same content for summary temporarily
        )
        return sage_response

    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to get sage response for {sage}: {e}")
        # Fallback to error response
        return SageResponse(
            answer=f"Error: {str(e)}",
            summary="Error invoking sage.",
        )


# Create the unified tool
philosophical_sage = StructuredTool.from_function(
    name="philosophical_sage",
    description=(
        "Provides philosophical wisdom from Marcus Aurelius (Stoic), "
        "Nassim Taleb (Antifragile), or Naval Ravikant (Modern Philosophy) "
        "based on the sage parameter"
    ),
    args_schema=PhilosophicalSageInput,
    coroutine=philosophical_sage_function,
)
