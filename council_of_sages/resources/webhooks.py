from typing import TYPE_CHECKING

import stripe
from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRouter
from loguru import logger

if TYPE_CHECKING:
    from stripe._error import SignatureVerificationError
else:
    from stripe.error import (
        SignatureVerificationError,  # type: ignore[attr-defined]
    )

from ..config import config
from ..lib.billing.webhook_handlers import (
    handle_payment_failed,
    handle_payment_succeeded,
)

# Initialize Stripe
stripe.api_key = config.stripe_secret_key

router = APIRouter(tags=["webhooks"])


@router.post(
    "/stripe/webhook",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid signature or malformed request"
        },
        status.HTTP_200_OK: {"description": "Webhook processed successfully"},
    },
    summary="Stripe Webhook Handler",
    description="Handle Stripe webhook events for payment processing",
)
async def stripe_webhook(request: Request) -> Response:
    """
    Handle Stripe webhook events for payment intent status changes.

    This endpoint processes Stripe webhook events with signature verification
    for security. It handles payment_intent.succeeded to credit user balances
    and payment_intent.payment_failed/canceled to record failed attempts.

    All operations are idempotent based on stripe_event_id and
    stripe_intent_id.

    Returns:
        200 response for all valid webhooks (including duplicates)

    Raises:
        HTTPException: 400 for signature verification failures
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.warning("Webhook received without Stripe signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.stripe_webhook_secret
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except SignatureVerificationError as e:
        logger.error(f"Invalid signature in Stripe webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    event_type = event["type"]
    event_id = event["id"]

    try:
        if event_type == "payment_intent.succeeded":
            intent = event["data"]["object"]
            await handle_payment_succeeded(intent, event_id)

        elif event_type in {
            "payment_intent.payment_failed",
            "payment_intent.canceled",
        }:
            intent = event["data"]["object"]
            await handle_payment_failed(intent, event_id)

        else:
            # Log but don't process other event types
            logger.debug(f"Received unhandled Stripe event: {event_type}")

    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Error processing Stripe webhook {event_id} ({event_type}): {e}"
        )
        # Return 200 to prevent Stripe retries for application errors
        # Log the error for manual investigation

    return Response(status_code=200)
