from decimal import Decimal
from typing import NamedTuple


class ModelPricing(NamedTuple):
    """Pricing information for a model"""

    input_usd_per_1m: Decimal
    output_usd_per_1m: Decimal
    tokenizer: str


# Pricing map for different models (prices in USD per 1M tokens)
MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI models
    "gpt-4o-mini": ModelPricing(
        input_usd_per_1m=Decimal("3.0000"),
        output_usd_per_1m=Decimal("6.0000"),
        tokenizer="openai",
    ),
    "gpt-4o": ModelPricing(
        input_usd_per_1m=Decimal("5.0000"),
        output_usd_per_1m=Decimal("15.0000"),
        tokenizer="openai",
    ),
    "gpt-4": ModelPricing(
        input_usd_per_1m=Decimal("30.0000"),
        output_usd_per_1m=Decimal("60.0000"),
        tokenizer="openai",
    ),
    "gpt-3.5-turbo": ModelPricing(
        input_usd_per_1m=Decimal("1.0000"),
        output_usd_per_1m=Decimal("1.0000"),
        tokenizer="openai",
    ),
    # Anthropic models
    "claude-3-5-haiku-20241022": ModelPricing(
        input_usd_per_1m=Decimal("1.5000"),
        output_usd_per_1m=Decimal("4.0000"),
        tokenizer="anthropic",
    ),
    "claude-sonnet-4-20250514": ModelPricing(
        input_usd_per_1m=Decimal("3.0000"),
        output_usd_per_1m=Decimal("6.0000"),
        tokenizer="anthropic",
    ),
    "claude-3-opus-20240229": ModelPricing(
        input_usd_per_1m=Decimal("15.0000"),
        output_usd_per_1m=Decimal("75.0000"),
        tokenizer="anthropic",
    ),
}


def get_model_pricing(model_name: str) -> ModelPricing:
    """Get pricing information for a model

    Args:
        model_name: Name of the model

    Returns:
        ModelPricing with pricing information

    Raises:
        ValueError: If model is not found in pricing map
    """
    if model_name not in MODEL_PRICING:
        raise ValueError(
            f"Model '{model_name}' not found in pricing map. "
            f"Available models: {list(MODEL_PRICING.keys())}"
        )
    return MODEL_PRICING[model_name]


def is_model_supported(model_name: str) -> bool:
    """Check if a model is supported

    Args:
        model_name: Name of the model

    Returns:
        True if model is supported, False otherwise
    """
    return model_name in MODEL_PRICING
