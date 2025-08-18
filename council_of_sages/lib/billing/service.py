from typing import Any

from fastapi import HTTPException, status
from loguru import logger
from mongoengine import NotUniqueError

from ...exc import PaymentRequiredError
from ...models.usage_event import UsageEvent
from ...models.user import User
from ...types import BillingInfo
from .calculator import calculate_cost_tenths_of_cents
from .token_count import count_input_tokens, count_output_tokens


async def process_billing(
    user_id: str,
    model_name: str,
    input_content: str | list[dict[str, Any]],
    output_content: str,
    request_id: str,
    response_metadata: dict[str, Any] | None = None,
    provider_request_id: str | None = None,
) -> BillingInfo:
    """Process billing for a completed LLM request

    Args:
        user_id: External user ID from auth provider
        model_name: Name of the model used
        input_content: Input prompt or messages
        output_content: Generated output content
        response_metadata: Optional response metadata with token counts
        request_id: Request ID for idempotency (required)
        provider_request_id: Optional provider request ID

    Returns:
        BillingInfo with usage details and updated balance

    Raises:
        ValueError: If model is not supported or other validation errors
    """
    # Get or create user
    user = await User.get_or_create(user_id)

    # Extract tokens from LangChain response metadata
    if response_metadata and "usage" in response_metadata:
        usage = response_metadata["usage"]
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
    else:
        # Fallback if metadata is missing
        logger.warning(
            "No usage metadata found for request, using fallback token "
            "counting"
        )
        input_tokens = count_input_tokens(model_name, input_content)
        output_tokens = count_output_tokens(
            model_name, output_content, response_metadata
        )

    # Calculate cost
    cost_tenths_of_cents = calculate_cost_tenths_of_cents(
        model_name, input_tokens, output_tokens
    )

    # Update user balance atomically
    await user.async_modify_balance(cost_tenths_of_cents)

    # Log usage event (with idempotency)
    try:
        usage_event = UsageEvent(
            user_internal_id=user.id,
            request_id=request_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_tenths_of_cents=cost_tenths_of_cents,
            provider_request_id=provider_request_id,
            status="success",
        )
        await usage_event.async_save()
        logger.debug(
            f"Logged usage event for user {user_id}: "
            f"{input_tokens} input + {output_tokens} output tokens, "
            f"cost: {cost_tenths_of_cents} tenths of cents"
        )
    except NotUniqueError:
        # Request already processed (idempotency)
        logger.info(
            f"Usage event already exists for user {user_id}, "
            f"request_id {request_id}"
        )

    # Create billing info
    return BillingInfo(
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_tenths_of_cents=cost_tenths_of_cents,
        balance=user.as_balance(),
    )


async def perform_pre_request_checks(user_id: str | None = None) -> str:
    """Perform pre-request checks for billing

    Args:
        user_id: Optional user ID (if not provided, gets from context)

    Returns:
        User ID from context or parameter

    Raises:
        HTTPException: If user not authenticated
        PaymentRequiredError: If insufficient funds
    """
    from ..auth.context import get_current_user_id

    # Get user from context if not provided
    if user_id is None:
        user_id = get_current_user_id()
        if not user_id:
            logger.error("No user ID found in context for billing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

    # Check balance
    has_balance = await check_user_balance(
        user_id, minimum_tenths_of_cents=-100
    )
    if not has_balance:
        logger.warning(f"User {user_id} has insufficient balance")
        raise PaymentRequiredError("Insufficient balance")

    return user_id


async def check_user_balance(
    user_id: str, minimum_tenths_of_cents: int = -100
) -> bool:
    """Check if user has sufficient balance for requests

    Args:
        user_id: External user ID from auth provider
        minimum_tenths_of_cents: Minimum balance threshold (default: -$0.10)

    Returns:
        True if balance is sufficient, False otherwise
    """
    user = await User.get_or_create(user_id)
    return user.balance_tenths_of_cents > minimum_tenths_of_cents


async def log_failed_usage(
    user_id: str,
    model_name: str,
    request_id: str,
    provider_request_id: str | None = None,
    error_message: str | None = None,
) -> None:
    """Log a failed usage event (no billing)

    Args:
        user_id: External user ID from auth provider
        model_name: Name of the model attempted
        request_id: Request ID for tracking (required)
        provider_request_id: Optional provider request ID
        error_message: Optional error message for logging
    """
    # Get or create user (to have internal ID for logging)
    user = await User.get_or_create(user_id)

    try:
        usage_event = UsageEvent(
            user_internal_id=user.id,
            request_id=request_id,
            model_name=model_name,
            input_tokens=0,
            output_tokens=0,
            cost_tenths_of_cents=0,
            provider_request_id=provider_request_id,
            status="failed",
        )
        await usage_event.async_save()
        logger.info(
            f"Logged failed usage event for user {user_id}: {error_message}"
        )
    except NotUniqueError:
        # Failed request already logged
        logger.debug(
            f"Failed usage event already exists for user {user_id}, "
            f"request_id {request_id}"
        )
