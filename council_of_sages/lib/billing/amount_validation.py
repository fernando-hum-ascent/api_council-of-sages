from decimal import Decimal, InvalidOperation

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
    # Parse once with robust error handling
    try:
        amount_decimal = Decimal(str(amount_usd))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValidationError(f"Invalid amount format: {amount_usd}") from e

    try:
        min_decimal = Decimal(str(min_usd))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValidationError(
            f"Invalid minimum amount format: {min_usd}"
        ) from e

    try:
        max_decimal = Decimal(str(max_usd))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValidationError(
            f"Invalid maximum amount format: {max_usd}"
        ) from e

    # Validate finiteness (reject NaN/Infinity)
    if not amount_decimal.is_finite():
        raise ValidationError(f"Invalid amount value: {amount_usd}")
    if not min_decimal.is_finite():
        raise ValidationError(f"Invalid minimum amount value: {min_usd}")
    if not max_decimal.is_finite():
        raise ValidationError(f"Invalid maximum amount value: {max_usd}")

    # Ensure min <= max
    if min_decimal > max_decimal:
        raise ValidationError(
            f"Minimum ${min_usd} cannot be greater than maximum ${max_usd}"
        )

    # Validate range using parsed Decimals
    if amount_decimal < min_decimal:
        raise ValidationError(
            f"Amount ${amount_usd} is below minimum ${min_usd}"
        )

    if amount_decimal > max_decimal:
        raise ValidationError(
            f"Amount ${amount_usd} exceeds maximum ${max_usd}"
        )

    # Convert to cents with proper rounding (guard against InvalidOperation)
    try:
        cents_decimal = amount_decimal * Decimal("100")
        amount_cents = int(cents_decimal.quantize(Decimal("1")))
    except InvalidOperation as e:
        raise ValidationError(f"Invalid amount format: {amount_usd}") from e

    return amount_cents


def cents_to_tenths_of_cents(amount_cents: int) -> int:
    """Convert Stripe cents to internal tenths-of-cents storage unit

    Args:
        amount_cents: Amount in cents from Stripe

    Returns:
        Amount in tenths of cents for internal balance storage
    """
    return amount_cents * 10
