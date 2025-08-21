from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

# Context variables for request-scoped data
current_user_id_var: ContextVar[str | None] = ContextVar(
    "current_user_id", default=None
)


def get_current_user_id() -> str | None:
    """Get current user ID from context

    Returns:
        User ID if available, None otherwise
    """
    return current_user_id_var.get()


def set_current_user_id(user_id: str) -> Token[str | None]:
    """Set current user ID in context

    Args:
        user_id: User ID to set
    """
    return current_user_id_var.set(user_id)


def reset_current_user_id(token: Token[str | None]) -> None:
    """Reset current user ID to previous state using the provided token."""
    current_user_id_var.reset(token)


@contextmanager
def user_id_context(user_id: str) -> Iterator[None]:
    """Context manager that sets the current user ID and guarantees reset.

    Usage:
        with user_id_context("user-123"):
            ...
    """
    token = current_user_id_var.set(user_id)
    try:
        yield
    finally:
        current_user_id_var.reset(token)


def clear_current_user_id() -> None:
    """Clear the current user ID from the context (set to None)."""
    current_user_id_var.set(None)
