import ast
import asyncio
import json
from typing import Any

import firebase_admin
from fastapi import HTTPException, status
from firebase_admin import auth, credentials
from firebase_admin.auth import ExpiredIdTokenError, InvalidIdTokenError
from loguru import logger


class FirebaseAuth:
    """Firebase Authentication service for token verification"""

    def __init__(
        self, project_id: str, service_account_key: str | None = None
    ) -> None:
        """Initialize Firebase Auth

        Args:
            project_id: Firebase project ID
            service_account_key: Service account JSON as string
        """
        self.project_id = project_id
        self._initialize_firebase(service_account_key)

    def _try_parse_service_account(self, raw_value: str) -> dict[str, Any]:
        """Attempt to parse the service account JSON handling common
        VS Code debugger quirks.
        """
        # 1) Standard JSON
        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, ValueError):
            logger.debug("Failed to parse as standard JSON")

        stripped = raw_value.strip()

        # 2) Strip a single pair of surrounding quotes then retry
        if (stripped.startswith("'") and stripped.endswith("'")) or (
            stripped.startswith('"') and stripped.endswith('"')
        ):
            inner = stripped[1:-1]
            try:
                return json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                # If it's a JSON string literal of the object,
                # unescape and retry
                try:
                    return json.loads(
                        inner.encode("utf-8").decode("unicode_escape")
                    )
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.debug("Failed to parse with unicode escape")

        # 3) Handle single-quoted, Python-dict-like strings using
        # ast.literal_eval
        try:
            evaluated = ast.literal_eval(stripped)
            if isinstance(evaluated, dict):
                return evaluated  # Looks like {'k': 'v'} style input
            if isinstance(evaluated, str):
                return json.loads(evaluated)
        except (ValueError, SyntaxError, json.JSONDecodeError):
            logger.debug("Failed to parse with ast.literal_eval")

        # 4) Last attempt: unescape then load
        try:
            unescaped = stripped.encode("utf-8").decode("unicode_escape")
            return json.loads(unescaped)
        except Exception as e:
            raise e

    def _initialize_firebase(self, service_account_key: str | None) -> None:
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase app is already initialized
            try:
                firebase_admin.get_app()
                logger.info("Firebase app already initialized")
                return
            except ValueError:
                # App not initialized, proceed with initialization
                pass

            if service_account_key:
                # Initialize with service account key from environment variable
                try:
                    try:
                        service_account_info = json.loads(service_account_key)
                    except (json.JSONDecodeError, ValueError):
                        # VS Code debugger fallback parsing
                        service_account_info = self._try_parse_service_account(
                            service_account_key
                        )
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(
                        f"Failed to parse FIREBASE_SERVICE_ACCOUNT_KEY. "
                        f"Check your .env file for proper JSON formatting "
                        f"and escaping: {e}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Invalid Firebase service account config",
                    )

                cred = credentials.Certificate(service_account_info)
                firebase_admin.initialize_app(
                    cred,
                    {
                        "projectId": self.project_id,
                    },
                )
            else:
                # Initialize with default credentials (for local development)
                # This assumes you have GOOGLE_APPLICATION_CREDENTIALS set
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(
                    cred,
                    {
                        "projectId": self.project_id,
                    },
                )

            logger.info(
                f"Firebase Admin SDK initialized for project: "
                f"{self.project_id}"
            )

        except (ValueError, FileNotFoundError) as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service initialization failed",
            )

    async def verify_token(self, id_token: str) -> dict[str, Any]:
        """Verify Firebase ID token and return user claims

        Args:
            id_token: Firebase ID token to verify

        Returns:
            Dict containing user claims from the token

        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Run token verification in thread pool since it's blocking
            decoded_token = await asyncio.to_thread(
                auth.verify_id_token, id_token, check_revoked=True
            )

            logger.debug(
                f"Token verified for user: {decoded_token.get('uid')}"
            )
            return decoded_token

        except ExpiredIdTokenError:
            logger.warning("Expired Firebase token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except InvalidIdTokenError as e:
            logger.warning(f"Invalid Firebase token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
            )
        except firebase_admin.auth.AuthError as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )

    def get_user_id_from_token(self, decoded_token: dict[str, Any]) -> str:
        """Extract user_id from verified token claims

        Args:
            decoded_token: Already verified token claims

        Returns:
            User ID from the token

        Raises:
            HTTPException: If user ID is missing from token
        """
        user_id = decoded_token.get("uid")
        if not user_id:
            logger.error("Token missing user ID (uid)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user identification",
            )

        return user_id
