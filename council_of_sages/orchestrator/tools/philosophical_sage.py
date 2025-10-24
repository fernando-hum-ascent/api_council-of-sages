from langchain_anthropic import ChatAnthropic
from loguru import logger

from ...lib.billing.billing_llm_proxy import BillingLLMProxy
from ...types import SageResponse
from ..prompt_modules import ROLE_SAGE_PROMPT
from ..sages_loader import build_prompt_for_predefined
from ..states import SageSpec


async def execute_sage_spec(
    sage_spec: SageSpec,
    user_query: str,
    chat_history: list[tuple[str, str]] | None = None,
) -> SageResponse:
    """Execute a sage based on SageSpec (predefined or dynamic)"""

    # Format chat history for context
    if chat_history:
        chat_context = "\n".join(
            [f"{role.upper()}: {content}" for role, content in chat_history]
        )
    else:
        chat_context = "No previous conversation context."

    try:
        # Determine which prompt to use
        if sage_spec.source == "predefined" and sage_spec.key:
            # Use YAML-based predefined sage
            from ..prompt_modules.predefined_sage_prompt import (
                PREDEFINED_SAGE_PROMPT,
            )

            formatted_prompt = build_prompt_for_predefined(
                sage_spec.key, user_query, chat_context
            )
            prompt_model = PREDEFINED_SAGE_PROMPT
        else:
            # Use generic role prompt for dynamic sages
            prompt_model = ROLE_SAGE_PROMPT
            formatted_prompt = prompt_model.template.format(
                name=sage_spec.name,
                description=sage_spec.description,
                original_user_query=user_query,
                chat_context=chat_context,
            )

        # Create and wrap LLM
        raw_llm = ChatAnthropic(
            model=prompt_model.model,
            temperature=prompt_model.temperature,
        )
        llm = BillingLLMProxy(raw_llm)

        # Invoke the LLM
        response = await llm.ainvoke(formatted_prompt)
        plain_response = str(response.content).strip()

        # Format response with sage name
        formatted_response = f"{plain_response}"

        return SageResponse(
            answer=formatted_response,
            summary=formatted_response,
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to get sage response for {sage_spec.name}: {e}")
        return SageResponse(
            answer=f"Error: {str(e)}",
            summary="Error invoking sage.",
        )
