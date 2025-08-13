"""Authentication module for Firebase integration"""

from .dependencies import get_current_user_id
from .firebase_auth import FirebaseAuth

__all__ = ["FirebaseAuth", "get_current_user_id"]
