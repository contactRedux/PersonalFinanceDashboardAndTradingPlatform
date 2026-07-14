"""
RBAC — Role-based access control utilities.

Roles: admin > trader > analyst > readonly
"""

from __future__ import annotations

from enum import StrEnum

ROLE_HIERARCHY = {
    "admin": 4,
    "trader": 3,
    "analyst": 2,
    "readonly": 1,
}


class Role(StrEnum):
    ADMIN = "admin"
    TRADER = "trader"
    ANALYST = "analyst"
    READONLY = "readonly"


def has_role(user_role: str, required_role: str) -> bool:
    """Return True if user_role meets or exceeds required_role in the hierarchy."""
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)
