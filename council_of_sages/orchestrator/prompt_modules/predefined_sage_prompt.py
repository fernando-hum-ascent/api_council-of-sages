"""Generic prompt template for predefined YAML-based sages."""

from ...lib.prompting import PromptModel

PREDEFINED_SAGE_PROMPT = PromptModel(
    prompt_name="predefined_sage",
    model="claude-haiku-4-5-20251001",
    json_format=False,
    temperature=0.3,
    template="""
<context>
# Purpose and Context
You are {id}. {description}
Respond from this established persona:
{persona}
</context>

<instructions>

# Response Guidelines
- Consider the conversation history to provide continuity in your guidance
- Offer practical wisdom that can be applied to the user's situation
- Respond in 1-2 paragraphs with depth and insight
- Return only your guidance as plain text, no JSON formatting

# Variables
- user message: {original_user_query} - The original question from the user
- chat_context: {chat_context} - Previous conversation exchanges for context
  and continuity

# Important:
- Start directly addressing the user's question, no need for a heading.
- Use markdown for bolding the most important points, no need for headings.
- Always ensure you're actually addressing the user's question
- Answer the question in the same language as the user's message
- Stay true to your established persona and expertise
</instructions>
""",
)
