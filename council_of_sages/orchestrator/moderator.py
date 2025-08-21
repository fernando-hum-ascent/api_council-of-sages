from typing import Any

from langchain_anthropic import ChatAnthropic

from ..lib.billing.billing_llm_proxy import BillingLLMProxy
from ..types import SageResponse
from .prompt_modules import (
    QUERY_DISTRIBUTION_PARSER,
    QUERY_DISTRIBUTION_PROMPT,
    RESPONSE_CONSOLIDATION_PROMPT,
)


class ResponseModerator:
    """Moderator that distributes queries and consolidates responses with
    conversation context"""

    def __init__(self) -> None:
        # Initialize LLMs using prompt model configurations and wrap with
        # billing proxy
        raw_distribution_llm = ChatAnthropic(
            model=QUERY_DISTRIBUTION_PROMPT.model,
            temperature=QUERY_DISTRIBUTION_PROMPT.temperature,
        )
        raw_consolidation_llm = ChatAnthropic(
            model=RESPONSE_CONSOLIDATION_PROMPT.model,
            temperature=RESPONSE_CONSOLIDATION_PROMPT.temperature,
        )

        # Wrap with billing proxy
        self.distribution_llm = BillingLLMProxy(raw_distribution_llm)
        self.consolidation_llm = BillingLLMProxy(raw_consolidation_llm)
        self.distribution_parser = QUERY_DISTRIBUTION_PARSER

    def _format_chat_context(
        self, chat_history: list[tuple[str, str]] | None
    ) -> str:
        """Format chat history for context in the prompt"""
        if not chat_history:
            return "No previous conversation context."

        return "\n".join(
            f"{role.upper()}: {content}" for role, content in chat_history
        )

    def _build_prompt(self, user_query: str, chat_context: str) -> str:
        """Build the formatted prompt for query distribution"""
        return QUERY_DISTRIBUTION_PROMPT.template.format(
            user_query=user_query,
            chat_context=chat_context,
            format_instructions=self.distribution_parser.get_format_instructions(),
        )

    def _extract_sage_queries(self, parsed_response: Any) -> dict[str, str]:
        """Extract non-empty sage queries from parsed response"""
        sage_fields = {
            "marcus_aurelius": parsed_response.marcus_aurelius,
            "nassim_taleb": parsed_response.nassim_taleb,
            "naval_ravikant": parsed_response.naval_ravikant,
        }

        return {name: query for name, query in sage_fields.items() if query}

    def _build_fallback_queries(
        self, user_query: str, chat_history: list[tuple[str, str]] | None
    ) -> dict[str, str]:
        """Build fallback queries when parsing fails"""
        context_note = (
            " (considering conversation history)" if chat_history else ""
        )

        return {
            "marcus_aurelius": (
                f"From a Stoic perspective, how should one approach"
                f"{context_note}: {user_query}"
            ),
            "nassim_taleb": (
                f"From an antifragile and probabilistic perspective"
                f"{context_note}: {user_query}"
            ),
            "naval_ravikant": (
                f"From an entrepreneurial and philosophical perspective"
                f"{context_note}: {user_query}"
            ),
        }

    def _build_distribution_result(
        self,
        rationale: str,
        parsed_response_data: dict[str, Any] | None,
        sage_queries: dict[str, str],
        user_query: str,
        chat_history: list[tuple[str, str]] | None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Build the standard distribution result format"""
        result = {
            "distribution_rationale": rationale,
            "parsed_response": parsed_response_data,
            "sage_queries": sage_queries,
            "user_query": user_query,
            "chat_context_length": len(chat_history) if chat_history else 0,
        }

        if error:
            result["error"] = error

        return result

    async def distribute_query(
        self,
        user_query: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Analyze user query with conversation context and create specific
        queries for selected relevant sages"""
        chat_context = self._format_chat_context(chat_history)
        formatted_prompt = self._build_prompt(user_query, chat_context)

        try:
            response = await self.distribution_llm.ainvoke(formatted_prompt)
            parsed_response = self.distribution_parser.parse(
                str(response.content)
            )
            sage_queries = self._extract_sage_queries(parsed_response)

            return self._build_distribution_result(
                parsed_response.distribution_rationale,
                parsed_response.model_dump(),
                sage_queries,
                user_query,
                chat_history,
            )

        except Exception as e:  # noqa: BLE001
            fallback_queries = self._build_fallback_queries(
                user_query, chat_history
            )
            rationale = f"Fallback distribution due to error: {str(e)}"

            return self._build_distribution_result(
                rationale,
                None,
                fallback_queries,
                user_query,
                chat_history,
                error=str(e),
            )

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
