from datetime import UTC, datetime

from mongoengine import DateTimeField, IntField, StringField
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field
from mongoengine_plus.models.event_handlers import updated_at


@updated_at.apply
class Payment(BaseModel, AsyncDocument):
    """Payment model for Stripe transactions with audit trail"""

    meta = {
        "collection": "payments",
        "indexes": [
            {"fields": ["stripe_intent_id"], "unique": True},
            {"fields": ["stripe_event_id"], "unique": True},
            {"fields": ["user_internal_id", "created_at"]},
        ],
    }

    # Primary key
    id = StringField(primary_key=True, default=uuid_field("PAY_"))

    # Stripe identifiers for idempotency
    stripe_intent_id = StringField(required=True, unique=True)
    stripe_event_id = StringField(required=True, unique=True)

    # User references
    user_internal_id = StringField(required=True)  # User.id
    user_id = StringField(required=True)  # User.user_id for easier queries

    # Payment amounts
    amount_cents = IntField(required=True)  # Stripe amount in cents
    currency = StringField(required=True, default="usd")

    # Status tracking
    status = StringField(
        required=True,
        choices=[
            "requires_payment_method",
            "processing",
            "succeeded",
            "failed",
            "canceled",
        ],
    )

    # Audit fields
    requested_amount_tenths_of_cents = IntField()  # From metadata
    credited_tenths_of_cents = IntField()  # What was actually credited

    # Timestamps
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
    updated_at = DateTimeField(default=lambda: datetime.now(UTC))

    @classmethod
    async def upsert_from_intent(
        cls,
        stripe_intent_id: str,
        stripe_event_id: str,
        user_internal_id: str,
        user_id: str,
        amount_cents: int,
        status: str,
        requested_amount_tenths_of_cents: int | None = None,
        credited_tenths_of_cents: int | None = None,
    ) -> "Payment":
        """Create or update payment record from Stripe intent

        Args:
            stripe_intent_id: Stripe PaymentIntent ID
            stripe_event_id: Stripe webhook event ID
            user_internal_id: User.id reference
            user_id: User.user_id reference
            amount_cents: Payment amount in cents
            status: Payment status
            requested_amount_tenths_of_cents: Original requested amount
            credited_tenths_of_cents: Amount credited to balance

        Returns:
            Payment instance
        """
        try:
            # Try to get existing payment by intent_id
            payment = await cls.objects.async_get(
                stripe_intent_id=stripe_intent_id
            )
            # Update status and credited amount if provided
            if payment.status != status:
                payment.status = status
            if credited_tenths_of_cents is not None:
                payment.credited_tenths_of_cents = credited_tenths_of_cents
            payment.updated_at = datetime.now(UTC)
            await payment.async_save()
            return payment
        except cls.DoesNotExist:
            # Check if event was already processed
            try:
                existing = await cls.objects.async_get(
                    stripe_event_id=stripe_event_id
                )
                # Event already processed, return existing
                return existing
            except cls.DoesNotExist:
                pass

            # Create new payment record
            payment = cls(
                stripe_intent_id=stripe_intent_id,
                stripe_event_id=stripe_event_id,
                user_internal_id=user_internal_id,
                user_id=user_id,
                amount_cents=amount_cents,
                status=status,
                requested_amount_tenths_of_cents=requested_amount_tenths_of_cents,
                credited_tenths_of_cents=credited_tenths_of_cents,
            )
            await payment.async_save()
            return payment
