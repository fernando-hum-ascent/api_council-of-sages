from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from loguru import logger

from ..lib.auth.dependencies import get_current_user_id
from ..models.user import User
from ..types import Balance

router = APIRouter(tags=["users"])


@router.get(
    "/users/me/balance",
    status_code=status.HTTP_200_OK,
    response_model=Balance,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid or missing authentication token"
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Database error"
        },
    },
    summary="Get User Balance",
    description="Get the current user's balance information",
)
async def get_user_balance(
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Balance:
    """
    Get the current user's balance information.

    **Authentication Required**: This endpoint requires a valid Firebase
    Bearer token in the Authorization header.

    Returns the user's current balance in tenths of cents and USD, along
    with the last update timestamp. If the user doesn't exist, creates a
    new user with the default balance (1000 tenths of cents = $1.00).

    Args:
        user_id: Automatically extracted from Firebase Bearer token

    Returns:
        Balance information with balance_tenths_of_cents, balance_usd,
        and updated_at

    Raises:
        HTTPException: 401 for authentication failures, 500 for database errors
    """
    try:
        # Get or create user with default balance
        user = await User.get_or_create(user_id)

        return user.as_balance()

    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to get balance for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user balance",
        )
