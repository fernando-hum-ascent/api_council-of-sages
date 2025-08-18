from typing import Any


def count_input_tokens(
    model_name: str, prompt_or_messages: str | list[dict[str, Any]]
) -> int:
    """Count input tokens for a model (fallback when no metadata available)

    Args:
        model_name: Name of the model
        prompt_or_messages: Input prompt string or messages list

    Returns:
        Number of input tokens (heuristic estimate)
    """
    # This is now primarily a fallback - LangChain metadata should be used
    # instead
    return _count_tokens_heuristic(prompt_or_messages)


def count_output_tokens(
    model_name: str,
    response_text_or_content: str,
    response_metadata: dict[str, Any] | None = None,
) -> int:
    """Count output tokens for a model (fallback when no metadata available)

    Args:
        model_name: Name of the model
        response_text_or_content: Response text content
        response_metadata: Optional response metadata with token counts

    Returns:
        Number of output tokens (heuristic estimate)
    """
    # This is now primarily a fallback - LangChain metadata should be used
    # instead
    return _count_tokens_heuristic(response_text_or_content)


def _count_tokens_heuristic(content: Any) -> int:
    """Heuristic token counting as fallback

    Args:
        content: Content to count tokens for

    Returns:
        Approximate number of tokens
    """
    if isinstance(content, str):
        # Rough approximation: 1 token ≈ 4 characters
        return len(content) // 4
    elif isinstance(content, list):
        # For messages/content lists, extract all text
        text = ""
        for item in content:
            if isinstance(item, dict):
                text += str(item.get("content", ""))
            else:
                text += str(item)
        return len(text) // 4
    else:
        # Convert to string and estimate
        return len(str(content)) // 4
