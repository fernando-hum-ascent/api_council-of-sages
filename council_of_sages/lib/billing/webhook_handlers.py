"""Stripe webhook handlers for payment processing."""

from loguru import logger

from ...models.payment import Payment
from ...models.user import User
from .amount_validation import cents_to_tenths_of_cents


async def handle_payment_succeeded(intent: dict, event_id: str) -> None:
    """Handle successful payment intent webhook

    Args:
        intent: Stripe PaymentIntent object
        event_id: Stripe event ID for idempotency
    """
    intent_id = intent["id"]
    try:
        amount_received = intent["amount_received"]
        user_id = intent["metadata"].get("user_id")
        requested_tenths_str = intent["metadata"].get(
            "requested_amount_tenths_of_cents"
        )
    except (KeyError, TypeError) as e:
        logger.error(f"Invalid intent structure for {intent_id}: {e}")
        return

    if not user_id:
        logger.error(f"PaymentIntent {intent_id} missing user_id in metadata")
        return

    try:
        requested_tenths = (
            int(requested_tenths_str) if requested_tenths_str else None
        )
    except ValueError:
        requested_tenths = None

    try:
        # Convert received amount to tenths of cents
        credited_tenths = cents_to_tenths_of_cents(amount_received)

        # Get or create user
        user = await User.get_or_create(user_id)

        # Upsert payment record with idempotency
        await Payment.upsert_from_intent(
            stripe_intent_id=intent_id,
            stripe_event_id=event_id,
            user_internal_id=user.id,
            user_id=user_id,
            amount_cents=amount_received,
            status="succeeded",
            requested_amount_tenths_of_cents=requested_tenths,
            credited_tenths_of_cents=credited_tenths,
        )

        # Atomically mark processed and credit once
        did_credit = await Payment.credit_if_not_processed(
            stripe_intent_id=intent_id,
            user=user,
            credited_tenths_of_cents=credited_tenths,
        )
        if did_credit:
            logger.info(
                f"Successfully credited {credited_tenths} tenths-of-cents "
                f"(${credited_tenths / 1000:.2f}) to user {user_id} "
                f"from PaymentIntent {intent_id}"
            )
        else:
            logger.info(
                f"""PaymentIntent {intent_id},
                 already processed for user {user_id}"""
            )
    except Exception as e:
        logger.error(f"Failed to process payment {intent_id}: {e}")
        raise  # Re-raise to signal webhook retry


async def handle_payment_failed(intent: dict, event_id: str) -> None:
    """Handle failed payment intent webhook

    Args:
        intent: Stripe PaymentIntent object
        event_id: Stripe event ID for idempotency
    """
    intent_id = intent["id"]
    user_id = intent["metadata"].get("user_id")
    amount = intent["amount"]
    requested_tenths_str = intent["metadata"].get(
        "requested_amount_tenths_of_cents"
    )

    if not user_id:
        logger.error(f"PaymentIntent {intent_id} missing user_id in metadata")
        return

    try:
        requested_tenths = (
            int(requested_tenths_str) if requested_tenths_str else None
        )
    except ValueError:
        requested_tenths = None

    # Get user for record keeping
    user = await User.get_or_create(user_id)

    # Record failed payment (no balance change)
    await Payment.upsert_from_intent(
        stripe_intent_id=intent_id,
        stripe_event_id=event_id,
        user_internal_id=user.id,
        user_id=user_id,
        amount_cents=amount,
        status="failed",
        requested_amount_tenths_of_cents=requested_tenths,
        credited_tenths_of_cents=None,  # No credit for failed payments
    )

    logger.info(f"Recorded failed payment for user {user_id}: {intent_id}")
