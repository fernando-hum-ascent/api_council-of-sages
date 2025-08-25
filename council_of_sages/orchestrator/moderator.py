from typing import Any

from langchain_anthropic import ChatAnthropic
from loguru import logger

from ..lib.billing.billing_llm_proxy import BillingLLMProxy
from ..types import SageResponse
from .prompt_modules import (
    RESPONSE_CONSOLIDATION_PROMPT,
    SAGE_SELECTION_PARSER,
    SAGE_SELECTION_PROMPT,
)
from .sages_loader import available_sages_text, list_sage_ids
from .states import SageSpec


class ResponseModerator:
    """Moderator that distributes queries and consolidates responses with
    conversation context"""

    def __init__(self) -> None:
        # Initialize LLMs using prompt model configurations and wrap with
        # billing proxy
        raw_selection_llm = ChatAnthropic(
            model=SAGE_SELECTION_PROMPT.model,
            temperature=SAGE_SELECTION_PROMPT.temperature,
        )
        raw_consolidation_llm = ChatAnthropic(
            model=RESPONSE_CONSOLIDATION_PROMPT.model,
            temperature=RESPONSE_CONSOLIDATION_PROMPT.temperature,
        )

        # Wrap with billing proxy
        self.selection_llm = BillingLLMProxy(raw_selection_llm)
        self.consolidation_llm = BillingLLMProxy(raw_consolidation_llm)
        self.selection_parser = SAGE_SELECTION_PARSER

    def _format_chat_context(
        self, chat_history: list[tuple[str, str]] | None
    ) -> str:
        """Format chat history for context in the prompt"""
        if not chat_history:
            return "No previous conversation context."

        return "\n".join(
            f"{role.upper()}: {content}" for role, content in chat_history
        )

    def _generate_available_sages_description(self) -> str:
        """Generate available predefined sages description from YAML files."""
        return available_sages_text()

    def _build_selection_prompt(
        self, user_query: str, chat_context: str
    ) -> str:
        """Build the formatted prompt for sage selection"""
        return SAGE_SELECTION_PROMPT.template.format(
            user_query=user_query,
            chat_context=chat_context,
            available_sages=self._generate_available_sages_description(),
            format_instructions=self.selection_parser.get_format_instructions(),
        )

    def _build_sage_specs_from_selection(
        self, parsed_response: Any
    ) -> list[SageSpec]:
        """Build list of SageSpec from sage selection response"""
        specs = []

        # Add predefined sages
        available_sage_ids = list_sage_ids()
        for sage_key in parsed_response.predefined_chosen_sages:
            if sage_key in available_sage_ids:
                specs.append(
                    SageSpec(
                        source="predefined",
                        key=sage_key,
                        name=sage_key.replace("_", " ").title(),
                        description="",  # Will be loaded dynamically
                    )
                )
            else:
                logger.warning(f"Unknown predefined sage key: {sage_key}")

        # Add dynamic sages
        for new_sage in parsed_response.new_sages_to_create:
            specs.append(
                SageSpec(
                    source="dynamic",
                    key=None,
                    name=new_sage.name,
                    description=new_sage.description,
                )
            )

        return specs

    def _build_fallback_sage_specs(self) -> list[SageSpec]:
        """Build fallback sage specs when parsing fails"""
        return [
            SageSpec(
                source="predefined",
                key="generalist_sage",
                name="Generalist Sage",
                description="",  # Will be loaded dynamically
            )
        ]

    async def select_sages(
        self,
        user_query: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> list[SageSpec]:
        """Select relevant sages (predefined and dynamic) for the user query"""
        chat_context = self._format_chat_context(chat_history)
        formatted_prompt = self._build_selection_prompt(
            user_query, chat_context
        )

        try:
            response = await self.selection_llm.ainvoke(formatted_prompt)
            parsed_response = self.selection_parser.parse(
                str(response.content)
            )
            sage_specs = self._build_sage_specs_from_selection(parsed_response)

            # Ensure we have at least one sage
            if not sage_specs:
                logger.warning("No sages selected, using fallback")
                sage_specs = self._build_fallback_sage_specs()

            return sage_specs

        except Exception as e:  # noqa: BLE001
            logger.error(f"Sage selection failed: {str(e)}, using fallback")
            return self._build_fallback_sage_specs()

    async def consolidate_responses(
        self,
        agent_responses: dict[str, SageResponse],
    ) -> str:
        """Consolidate multiple sage responses into a single coherent response
        with conversation context"""

        # Transform structured responses into answers and summaries
        sage_answers = {}
        sage_summaries = {}

        for sage_name, response in agent_responses.items():
            if sage_name != "error":  # Skip error responses
                # Handle both SageResponse objects and dict format
                if hasattr(response, "answer"):
                    sage_answers[sage_name] = response.answer
                    sage_summaries[sage_name] = response.summary
                elif isinstance(response, dict):
                    sage_answers[sage_name] = response.get(
                        "answer", str(response)
                    )
                    sage_summaries[sage_name] = response.get("summary", "")
                else:
                    sage_answers[sage_name] = str(response)
                    sage_summaries[sage_name] = ""

        # For now, return a simple concatenation of answers
        # Future: use RESPONSE_CONSOLIDATION_PROMPT with structured data
        sage_outputs = "\n\n".join(
            [
                f"""=== {sage_name.upper().replace("_", " ")} ===
{answer}"""
                for sage_name, answer in sage_answers.items()
            ]
        )
        return sage_outputs
