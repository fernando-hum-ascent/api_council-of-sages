from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field

from ...lib.billing.billing_llm_proxy import BillingLLMProxy
from ...types import SageEnum
from ..prompt_modules import (
    MARCUS_AURELIUS_PROMPT,
    NASSIM_TALEB_PROMPT,
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
SAGE_CONFIGS = {
    SageEnum.marcus_aurelius: {
        "prompt": MARCUS_AURELIUS_PROMPT,
        "response_header": "MARCUS AURELIUS REFLECTS:",
        "response_footer": "*From the Meditations of Marcus Aurelius*",
    },
    SageEnum.nassim_taleb: {
        "prompt": NASSIM_TALEB_PROMPT,
        "response_header": "NASSIM TALEB RESPONDS:",
        "response_footer": "*With characteristic Talebian skepticism*",
    },
    SageEnum.naval_ravikant: {
        "prompt": NAVAL_RAVIKANT_PROMPT,
        "response_header": "NAVAL RAVIKANT SHARES:",
        "response_footer": "*Wisdom for the modern age*",
    },
}


async def philosophical_sage_function(
    sage: SageEnum, query: str, state: OrchestratorState
) -> str:
    """Unified sage function that provides wisdom based on the specified
    sage parameter"""

    # Get sage-specific configuration
    config = SAGE_CONFIGS[sage]
    prompt_model = config["prompt"]

    # Get the pre-wrapped LLM instance
    llm = _get_sage_llm(sage)

    # Type assertion for mypy
    assert hasattr(prompt_model, "template")

    # Extract chat history from injected state
    chat_history = state.get("chat_history", [])

    # Format chat history for context
    if chat_history:
        chat_context = "\\n".join(
            [
                f"{role.upper()}: {content}"
                for role, content in chat_history[-3:]
            ]
        )
    else:
        chat_context = "No previous conversation context."

    # Format the prompt with the query and context using the PromptModel
    # template
    formatted_prompt = prompt_model.template.format(
        query=query, chat_context=chat_context
    )

    # Invoke the LLM
    response = await llm.ainvoke(formatted_prompt)

    # Return the response with sage-specific formatting
    sage_response = f"""{config["response_header"]}

{response.content}
"""
    return sage_response


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
