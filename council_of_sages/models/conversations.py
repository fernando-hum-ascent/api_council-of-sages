from datetime import UTC, datetime

from mongoengine import DateTimeField, DoesNotExist, StringField
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field
from mongoengine_plus.models.event_handlers import updated_at

from ..types import ChatUserEnum
from .messages import Message


@updated_at.apply
class Conversation(BaseModel, AsyncDocument):
    """Conversation model for storing chat metadata"""

    meta = {
        "collection": "conversations",
        "indexes": [
            "user_id",
        ],
    }

    id = StringField(primary_key=True, default=uuid_field("CONV_"))
    user_id = StringField(required=True)
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
    updated_at = DateTimeField(default=lambda: datetime.now(UTC))

    async def get_chat_history_with_summaries(self) -> list[tuple[str, str]]:
        """Get recent chat history with summaries for context"""
        messages = (
            await Message.objects.filter(conversation_id=self.id)
            .order_by("timestamp")
            .limit(50)
            .async_to_list()
        )

        if not messages:
            return []

        def extract_content(msg: Message) -> str:
            """Extract message content, preferring summary for AI messages"""
            if msg.role == ChatUserEnum.ai and msg.summary:
                return msg.summary
            return msg.content

        # Group messages into interactions (human query + AI responses)
        interactions: list[list[Message]] = []
        current: list[Message] = []

        for msg in messages:
            # Start new interaction on human message or turn_id change
            if msg.role == ChatUserEnum.human or (
                msg.turn_id and current and msg.turn_id != current[0].turn_id
            ):
                if current:
                    interactions.append(current)
                    current = []
            current.append(msg)

        if current:
            interactions.append(current)

        # Return last 3 interactions formatted as (role, content) tuples
        return [
            (
                "human" if msg.role == ChatUserEnum.human else "ai",
                extract_content(msg),
            )
            for interaction in interactions[-3:]
            for msg in interaction
        ]


async def get_active_conversation_or_create_one(
    user_id: str, conversation_id: str | None = None
) -> Conversation:
    try:
        return await Conversation.objects.async_get(
            id=conversation_id, user_id=user_id
        )
    except DoesNotExist:
        conversation = Conversation(user_id=user_id)
        await conversation.async_save()
        return conversation
