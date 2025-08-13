from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from .firebase_auth import FirebaseAuth

# Initialize HTTPBearer security scheme
security = HTTPBearer(
    scheme_name="Firebase Bearer Token",
    description="Firebase ID token for authentication",
)

# Global Firebase auth instance (will be set during app startup)
_firebase_auth: FirebaseAuth | None = None


def get_firebase_auth() -> FirebaseAuth:
    """Get the global Firebase auth instance

    Returns:
        FirebaseAuth instance

    Raises:
        HTTPException: If Firebase auth is not initialized
    """
    if _firebase_auth is None:
        logger.error("Firebase authentication not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service not available",
        )
    return _firebase_auth


def set_firebase_auth(firebase_auth: FirebaseAuth) -> None:
    """Set the global Firebase auth instance (called during app startup)"""
    global _firebase_auth
    _firebase_auth = firebase_auth


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    """Extract and validate user ID from Firebase Bearer token

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        Verified user ID from Firebase token

    Raises:
        HTTPException: If token is invalid, expired, or missing user ID
    """
    try:
        # Get Firebase auth instance
        firebase_auth = get_firebase_auth()

        # Extract token from credentials
        token = credentials.credentials
        logger.debug("Verifying Firebase token")

        # Verify token with Firebase
        decoded_token = await firebase_auth.verify_token(token)

        # Extract user ID from verified token
        user_id = firebase_auth.get_user_id_from_token(decoded_token)

        logger.debug(f"Authentication successful for user: {user_id}")
        return user_id

    except HTTPException:
        # Re-raise HTTP exceptions (these are already properly formatted)
        raise
    except ValueError as e:
        # Log unexpected errors and return generic auth failure
        logger.error(f"Unexpected authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
