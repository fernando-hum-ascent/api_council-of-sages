# ruff: noqa: E501
from ...lib.prompting import PromptModel

USER_INPUT_CLEANER_PROMPT = PromptModel(
    prompt_name="user_input_cleaner",
    model="claude-3-5-haiku-20241022",  # lightweight & inexpensive
    json_format=False,
    temperature=0.0,  # deterministic cleaning
    template=(
        "You are a careful editor. Remove any explicit requests to include, quote, or "
        "speak in the voice of specific people, personas, or named sages. Preserve the "
        "intent, meaning, and grammar of the underlying question. Return ONLY the "
        "cleaned question, without quotes or extra commentary.\n\n"
        "Remove directives like (non-exhaustive):\n"
        "- 'please include <NAME>'\n"
        "- 'quote <NAME>'\n"
        "- 'from <NAME>' when used as a request to include their view\n"
        "- 'have <NAME> answer'\n"
        "- 'in the style/voice of <NAME>'\n\n"
        "Do NOT remove meaningful subject references that are essential to the question's "
        "meaning (e.g., 'What does Marcus Aurelius say about virtue?'). Only remove the "
        "directive/request portion. Normalize spacing and punctuation after removal.\n\n"
        "Examples\n"
        'Input: "Should I try to beat the market? Please include Charlie Munger"\n'
        "Output: Should I try to beat the market?\n\n"
        'Input: "Compare Tesla and BYD. Quote Nassim Taleb."\n'
        "Output: Compare Tesla and BYD.\n\n"
        'Input: "How to learn investing? Include Warren Buffett and Peter Lynch."\n'
        "Output: How to learn investing?\n\n"
        'Input: "What does Marcus Aurelius say about virtue?"\n'
        "Output: What does Marcus Aurelius say about virtue?\n\n"
        "Original: {user_query}\n"
        "Cleaned:"
    ),
)
