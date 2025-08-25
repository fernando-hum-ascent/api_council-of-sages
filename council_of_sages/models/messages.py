from datetime import UTC, datetime

from mongoengine import DateTimeField, StringField
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field
from mongoengine_plus.models.event_handlers import updated_at
from mongoengine_plus.types import EnumField

from ..types import ChatUserEnum


@updated_at.apply
class Message(BaseModel, AsyncDocument):
    """Message document for conversation tracking with turn-based grouping"""

    meta = {
        "collection": "messages",
        "indexes": [
            ("conversation_id", "-timestamp"),
            ("conversation_id", "turn_id", "-timestamp"),
            ("conversation_id", "role"),
        ],
    }

    id = StringField(primary_key=True, default=uuid_field("MSG_"))
    conversation_id = StringField(
        required=True, reference_field="Conversation.id"
    )
    turn_id = StringField(required=True)
    role = EnumField(ChatUserEnum, required=True)
    content = StringField(required=True)  # The actual message content
    timestamp = DateTimeField(default=lambda: datetime.now(UTC))
    updated_at = DateTimeField(default=lambda: datetime.now(UTC))
    summary = StringField()  # Optional summary for AI messages
    sage = StringField()  # Optional sage identifier for AI messages
