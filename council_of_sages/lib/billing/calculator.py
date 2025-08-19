from decimal import ROUND_HALF_UP, Decimal

from .costs import get_model_pricing


def calculate_cost_tenths_of_cents(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    multiplier: float = 3.0,
) -> int:
    """Calculate cost in integer tenths of cents for a model usage

    Args:
        model_name: Name of the model
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        multiplier: Multiplier to apply to the final cost (default: 3.0)

    Returns:
        Cost in integer tenths of cents (0.1 cent precision)

    Raises:
        ValueError: If model is not found in pricing map
    """
    pricing = get_model_pricing(model_name)

    # Calculate costs using Decimal for precision
    input_cost_usd = (
        Decimal(input_tokens) / Decimal(1000000)
    ) * pricing.input_usd_per_1m
    output_cost_usd = (
        Decimal(output_tokens) / Decimal(1000000)
    ) * pricing.output_usd_per_1m
    total_usd = input_cost_usd + output_cost_usd

    # Apply multiplier
    total_usd = total_usd * Decimal(str(multiplier))

    # Convert to integer tenths of cents with proper rounding
    return int(
        (total_usd * Decimal(1000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def calculate_cost_usd(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    multiplier: float = 3.0,
) -> float:
    """Calculate cost in USD for a model usage

    Args:
        model_name: Name of the model
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        multiplier: Multiplier to apply to the final cost (default: 1.0)

    Returns:
        Cost in USD as float

    Raises:
        ValueError: If model is not found in pricing map
    """
    cost_tenths_of_cents = calculate_cost_tenths_of_cents(
        model_name, input_tokens, output_tokens, multiplier
    )
    return cost_tenths_of_cents / 1000.0
