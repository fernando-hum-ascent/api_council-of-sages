from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .prompt_modules import (
    QUERY_DISTRIBUTION_PROMPT,
    RESPONSE_CONSOLIDATION_PROMPT,
)


class QueryDistributionOutput(BaseModel):
    """Output model for query distribution decisions"""

    marcus_query: str = Field(
        description="Specific query for Marcus Aurelius sage"
    )
    taleb_query: str = Field(
        description="Specific query for Nassim Taleb sage"
    )
    naval_query: str = Field(
        description="Specific query for Naval Ravikant sage"
    )
    distribution_rationale: str = Field(
        description="Explanation of why queries were distributed this way"
    )


class ResponseModerator:
    """Moderator that distributes queries and consolidates responses with
    conversation context"""

    def __init__(self) -> None:
        # Initialize LLMs using prompt model configurations
        self.distribution_llm = ChatAnthropic(
            model=QUERY_DISTRIBUTION_PROMPT.model,
            temperature=QUERY_DISTRIBUTION_PROMPT.temperature,
        )
        self.consolidation_llm = ChatAnthropic(
            model=RESPONSE_CONSOLIDATION_PROMPT.model,
            temperature=RESPONSE_CONSOLIDATION_PROMPT.temperature,
        )
        self.distribution_parser: PydanticOutputParser[
            QueryDistributionOutput
        ] = PydanticOutputParser(pydantic_object=QueryDistributionOutput)

    async def distribute_query(
        self,
        user_query: str,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> dict[str, str]:
        """Analyze user query with conversation context and create specific
        queries for each sage"""

        # Format chat history for context
        if chat_history:
            chat_context = "\n".join(
                [
                    f"{role.upper()}: {content}"
                    for role, content in chat_history[-5:]
                ]
            )  # Last 5 exchanges
        else:
            chat_context = "No previous conversation context."

        # Format the prompt using the PromptModel template
        formatted_prompt = QUERY_DISTRIBUTION_PROMPT.template.format(
            user_query=user_query,
            chat_context=chat_context,
            format_instructions=self.distribution_parser.get_format_instructions(),
        )

        try:
            response = await self.distribution_llm.ainvoke(formatted_prompt)
            parsed_response = self.distribution_parser.parse(
                str(response.content)
            )

            return {
                "marcus_aurelius": parsed_response.marcus_query,
                "nassim_taleb": parsed_response.taleb_query,
                "naval_ravikant": parsed_response.naval_query,
                "distribution_rationale": (
                    parsed_response.distribution_rationale
                ),
            }

        except Exception as e:  # noqa: BLE001
            # Fallback: send the original query to all sages with context
            # awareness
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
                "distribution_rationale": (
                    f"Fallback distribution due to error: {str(e)}"
                ),
            }

    async def consolidate_responses(
        self,
        user_query: str,
        agent_queries: dict[str, str],
        agent_responses: dict[str, str],
        chat_history: list[tuple[str, str]] | None = None,
    ) -> str:
        """Consolidate multiple sage responses into a single coherent response
        with conversation context"""

        # Format chat history for context
        if chat_history:
            conversation_context = "\n".join(
                [
                    f"{role.upper()}: {content}"
                    for role, content in chat_history[-3:]
                ]
            )
        else:
            conversation_context = "No previous conversation context."

        # Prepare the consolidation prompt
        query_context = "\n".join(
            [
                f"• {sage_name.replace('_', ' ').title()}: {query}"
                for sage_name, query in agent_queries.items()
                if not sage_name == "distribution_rationale"
            ]
        )

        sage_outputs = "\n\n".join(
            [
                f"=== {sage_name.upper().replace('_', ' ')} ===\n{response}"
                for sage_name, response in agent_responses.items()
            ]
        )

        # Format the consolidation prompt using the PromptModel template
        formatted_prompt = RESPONSE_CONSOLIDATION_PROMPT.template.format(
            conversation_context=conversation_context,
            user_query=user_query,
            query_context=query_context,
            sage_outputs=sage_outputs,
        )

        response = await self.consolidation_llm.ainvoke(formatted_prompt)
        return str(response.content)
