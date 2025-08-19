from typing import Any


class BaseAppError(Exception):
    """Base exception for application-specific errors"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(Exception):
    """Base class for authentication errors"""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when Firebase token is expired"""

    pass


class InvalidTokenError(AuthenticationError):
    """Raised when Firebase token is invalid"""

    pass


class AuthenticationServiceError(AuthenticationError):
    """Raised when authentication service is unavailable"""

    pass


class PaymentRequiredError(BaseAppError):
    """Raised when user has insufficient funds for LLM requests"""

    def __init__(
        self,
        message: str = "Insufficient balance",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="PAYMENT_REQUIRED",
            details=details or {},
        )


class ValidationError(BaseAppError):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details or {},
        )
