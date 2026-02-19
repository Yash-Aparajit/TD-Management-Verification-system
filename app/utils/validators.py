"""
Password and input validation. Used by auth and user management.
"""
import re
from ..config import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIRE_NUMBER,
    PASSWORD_REQUIRE_LETTER,
    PASSWORD_REQUIRE_SYMBOL,
)


def validate_password(password):
    """
    Returns (True, None) if valid, else (False, error_message).
    Rules: min 10 chars, at least one number, one letter, one symbol.
    """
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if PASSWORD_REQUIRE_NUMBER and not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if PASSWORD_REQUIRE_LETTER and not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain at least one letter."
    if PASSWORD_REQUIRE_SYMBOL and not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
        return False, "Password must contain at least one symbol."
    return True, None


def normalize_fg_code(value):
    return (value or "").strip().upper()


def normalize_unit(value):
    return (value or "").strip() or "PCS"


def normalize_whitespace(value):
    return (value or "").strip() if value else ""
