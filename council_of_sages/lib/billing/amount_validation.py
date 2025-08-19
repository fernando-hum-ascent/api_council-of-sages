from decimal import Decimal

from ...exc import ValidationError


def validate_amount_usd_and_to_cents(
    amount_usd: float, min_usd: float, max_usd: float
) -> int:
    """Validate USD amount and convert to cents for Stripe

    Args:
        amount_usd: Amount in USD to validate
        min_usd: Minimum allowed amount in USD
        max_usd: Maximum allowed amount in USD

    Returns:
        Amount in cents for Stripe API

    Raises:
        ValidationError: If amount is invalid or out of range
    """
    # Use Decimal for precise currency calculations
    try:
        amount_decimal = Decimal(str(amount_usd))
    except (ValueError, TypeError) as e:
        raise ValidationError(f"Invalid amount format: {amount_usd}") from e

    # Validate range
    if amount_decimal < Decimal(str(min_usd)):
        raise ValidationError(
            f"Amount ${amount_usd} is below minimum ${min_usd}"
        )

    if amount_decimal > Decimal(str(max_usd)):
        raise ValidationError(
            f"Amount ${amount_usd} exceeds maximum ${max_usd}"
        )

    # Convert to cents with proper rounding
    cents_decimal = amount_decimal * Decimal("100")
    amount_cents = int(cents_decimal.quantize(Decimal("1")))

    return amount_cents


def cents_to_tenths_of_cents(amount_cents: int) -> int:
    """Convert Stripe cents to internal tenths-of-cents storage unit

    Args:
        amount_cents: Amount in cents from Stripe

    Returns:
        Amount in tenths of cents for internal balance storage
    """
    return amount_cents * 10
