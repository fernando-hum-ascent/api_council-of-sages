from datetime import UTC, datetime

from mongoengine import (
    DateTimeField,
    DoesNotExist,
    DynamicField,
    EmbeddedDocument,
    EmbeddedDocumentField,
    ListField,
    StringField,
)
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field
from mongoengine_plus.models.event_handlers import updated_at
from mongoengine_plus.types import EnumField

from ..types import ChatUserEnum


class Message(EmbeddedDocument):
    """Individual message in a conversation"""

    id = StringField(primary_key=True, default=uuid_field("MSG_"))
    role = EnumField(ChatUserEnum, required=True)  # 'human' or 'ai'
    content = DynamicField(
        required=True
    )  # Supports both string and dict content
    timestamp = DateTimeField(default=lambda: datetime.now(UTC))


@updated_at.apply
class Conversation(BaseModel, AsyncDocument):
    """Conversation model for storing chat history"""

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
    messages = ListField(EmbeddedDocumentField(Message), default=list)

    async def add_message(
        self, content: str | dict, role: ChatUserEnum
    ) -> None:
        """Add a new message to the conversation"""
        self.messages.append(
            Message(
                role=role.value,
                content=content,
                timestamp=datetime.now(UTC),
            )
        )
        await self.async_save()

    def get_chat_history(self) -> list[tuple[str, str]]:
        """Convert messages to chat history format for LangChain"""
        chat_history = []
        for message in self.messages:
            role = "human" if message.role == ChatUserEnum.human else "ai"
            content = message.content
            # Convert dict content to string if needed
            if isinstance(content, dict):
                content = str(content)
            chat_history.append((role, content))
        return chat_history


async def get_active_conversation_or_create_one(
    user_id: str, conversation_id: str | None = None
) -> Conversation:
    """Get existing conversation or create a new one"""
    try:
        if conversation_id:
            return await Conversation.objects.async_get(
                id=conversation_id, user_id=user_id
            )
        else:
            # Create new conversation if no ID provided
            conversation = Conversation(user_id=user_id)
            await conversation.async_save()
            return conversation
    except DoesNotExist:
        # Create new conversation if specified ID doesn't exist
        conversation = Conversation(user_id=user_id)
        await conversation.async_save()
        return conversation
