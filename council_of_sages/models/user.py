from datetime import UTC, datetime

from mongoengine import DateTimeField, DoesNotExist, IntField, StringField
from mongoengine_plus.aio import AsyncDocument
from mongoengine_plus.models import BaseModel, uuid_field
from mongoengine_plus.models.event_handlers import updated_at

from ..types import Balance


@updated_at.apply
class User(BaseModel, AsyncDocument):
    """User model with balance tracking for billing"""

    meta = {
        "collection": "users",
        "indexes": [
            {"fields": ["user_id"], "unique": True},
        ],
    }

    id = StringField(primary_key=True, default=uuid_field("USR_"))
    user_id = StringField(required=True, unique=True)  # external id from auth
    balance_tenths_of_cents = IntField(
        required=True, default=1000
    )  # 1 USD default
    created_at = DateTimeField(default=lambda: datetime.now(UTC))
    updated_at = DateTimeField(default=lambda: datetime.now(UTC))

    @classmethod
    async def get_or_create(cls, user_id: str) -> "User":
        """Get existing user or create new one with default balance

        Args:
            user_id: External user ID from auth provider

        Returns:
            User instance
        """
        try:
            return await cls.objects.async_get(user_id=user_id)
        except DoesNotExist:
            user = cls(user_id=user_id)
            await user.async_save()
            return user

    def as_balance(self) -> Balance:
        """Convert to Balance Pydantic model

        Returns:
            Balance model with current user balance info
        """
        return Balance(
            balance_tenths_of_cents=self.balance_tenths_of_cents,
            balance_usd=self.balance_tenths_of_cents / 1000.0,
            updated_at=self.updated_at,
        )

    def as_balance_dict(self) -> dict[str, int | float | datetime]:
        """Convert balance to dictionary

        Returns:
            Dictionary with balance information
        """
        return self.as_balance().model_dump()

    async def async_modify_balance(self, amount_tenths_of_cents: int) -> None:
        """Atomically modify user balance

        Args:
            amount_tenths_of_cents: Amount to subtract from balance
                (positive = deduction)
        """
        # Use MongoDB's atomic $inc operation for thread-safe balance updates
        await self.__class__.objects.filter(id=self.id).async_update(
            dec__balance_tenths_of_cents=amount_tenths_of_cents
        )
        # Reload to get updated balance
        reloaded_user = await self.__class__.objects.async_get(id=self.id)
        self.balance_tenths_of_cents = reloaded_user.balance_tenths_of_cents
        self.updated_at = reloaded_user.updated_at

    @classmethod
    async def get_current_balance(cls, user_id: str) -> Balance:
        """Get current balance for a user ID

        Args:
            user_id: External user ID from auth provider

        Returns:
            Balance model with current user balance info
        """
        user = await cls.get_or_create(user_id)
        return user.as_balance()
