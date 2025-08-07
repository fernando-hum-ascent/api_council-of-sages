from langchain_anthropic import ChatAnthropic
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ...types import SageEnum
from ..prompt_modules import (
    MARCUS_AURELIUS_PROMPT,
    NASSIM_TALEB_PROMPT,
    NAVAL_RAVIKANT_PROMPT,
)


class PhilosophicalSageInput(BaseModel):
    """Input model for the unified philosophical sage tool"""

    sage: SageEnum = Field(description="Which philosophical sage to consult")
    query: str = Field(description="Query for the sage")
    chat_history: list[tuple[str, str]] = Field(
        default=[], description="Previous conversation context"
    )


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
    sage: SageEnum,
    query: str,
    chat_history: list[tuple[str, str]] | None = None,
) -> str:
    """Unified sage function that provides wisdom based on the specified
    sage parameter"""

    # Get sage-specific configuration
    config = SAGE_CONFIGS[sage]
    prompt_model = config["prompt"]

    # Type assertion for mypy
    assert hasattr(prompt_model, "model")
    assert hasattr(prompt_model, "temperature")
    assert hasattr(prompt_model, "template")

    # Create LLM instance with sage-specific settings from prompt model
    llm = ChatAnthropic(
        model=prompt_model.model,
        temperature=prompt_model.temperature,
    )

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
    sage_response = f"""
{config["response_header"]}

{response.content}

{config["response_footer"]}
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
