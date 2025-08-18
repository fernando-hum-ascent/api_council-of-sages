from datetime import UTC, datetime

from mongoengine import DateTimeField, IntField, StringField
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field


class UsageEvent(BaseModel, AsyncDocument):
    """Usage event model for auditing and analytics"""

    meta = {
        "collection": "usage_events",
        "indexes": [
            # Unique compound index for idempotency
            {
                "fields": ["user_internal_id", "request_id"],
                "unique": True,
            },
            # Secondary indexes for queries
            "user_internal_id",
            "created_at",
        ],
    }

    id = StringField(primary_key=True, default=uuid_field("UE_"))
    user_internal_id = StringField(required=True)  # USR_xxx
    request_id = StringField(
        required=True
    )  # Unique per LLM call for idempotency
    model_name = StringField(required=True)
    input_tokens = IntField(required=True, default=0)
    output_tokens = IntField(required=True, default=0)
    cost_tenths_of_cents = IntField(required=True, default=0)
    provider_request_id = StringField()  # Optional provider request ID
    status = StringField(
        required=True, choices=["success", "failed"], default="success"
    )
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
