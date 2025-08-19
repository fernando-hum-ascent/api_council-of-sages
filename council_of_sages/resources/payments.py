from typing import Annotated

import stripe
from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from ..config import config
from ..exc import ValidationError
from ..lib.auth.dependencies import get_current_user_id
from ..lib.billing.amount_validation import (
    cents_to_tenths_of_cents,
    validate_amount_usd_and_to_cents,
)

# Initialize Stripe
stripe.api_key = config.stripe_secret_key

router = APIRouter(tags=["payments"])


class CreateIntentRequest(BaseModel):
    """Request model for creating payment intent"""

    amount_usd: float = Field(gt=0, description="Amount to charge in USD")


class CreateIntentResponse(BaseModel):
    """Response model for payment intent creation"""

    client_secret: str = Field(description="Stripe client secret")
    intent_id: str = Field(description="Stripe PaymentIntent ID")
    amount_cents: int = Field(description="Amount in cents")
    currency: str = Field(description="Currency code")
    status: str = Field(description="Payment intent status")


@router.post(
    "/payments/create-payment-intent",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateIntentResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid amount or validation error"
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing authentication token"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Stripe API or server error"
        },
    },
    summary="Create Payment Intent",
    description="Create a Stripe PaymentIntent for user balance top-up",
)
async def create_payment_intent(
    req: CreateIntentRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> CreateIntentResponse:
    """
    Create a Stripe PaymentIntent for adding funds to user balance.

    **Authentication Required**: This endpoint requires a valid Firebase
    Bearer token in the Authorization header.

    The server validates the requested amount against configured min/max
    limits and creates a PaymentIntent with Stripe. The actual balance
    credit happens only after successful payment via webhook.

    Args:
        req: Request containing amount_usd to charge
        user_id: Automatically extracted from Firebase Bearer token

    Returns:
        Payment intent details including client_secret for Stripe.js

    Raises:
        HTTPException: 400 for validation errors, 401 for auth, 500 for API
            errors
    """
    try:
        # Validate amount and convert to cents
        amount_cents = validate_amount_usd_and_to_cents(
            req.amount_usd,
            config.payments_min_topup_usd,
            config.payments_max_topup_usd,
        )

        # Calculate requested tenths for audit
        requested_tenths = cents_to_tenths_of_cents(amount_cents)

        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            automatic_payment_methods={"enabled": True},
            metadata={
                "user_id": user_id,
                "requested_amount_tenths_of_cents": str(requested_tenths),
            },
        )

        logger.info(
            f"Created PaymentIntent {intent.id} for user {user_id}: "
            f"${req.amount_usd} ({amount_cents} cents)"
        )

        return CreateIntentResponse(
            client_secret=intent.client_secret,
            intent_id=intent.id,
            amount_cents=amount_cents,
            currency="usd",
            status=intent.status,
        )

    except ValidationError as e:
        logger.warning(
            f"Payment validation failed for user {user_id}: "
            f"${req.amount_usd} - {e.message}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe API error for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment service temporarily unavailable",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Unexpected error creating PaymentIntent for user {user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
