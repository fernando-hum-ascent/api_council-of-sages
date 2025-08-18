from contextvars import ContextVar

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


def set_current_user_id(user_id: str) -> None:
    """Set current user ID in context

    Args:
        user_id: User ID to set
    """
    current_user_id_var.set(user_id)
