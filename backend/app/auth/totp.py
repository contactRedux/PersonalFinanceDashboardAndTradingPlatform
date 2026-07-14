"""
TOTP (Time-based One-Time Password) for 2FA.
Uses pyotp — RFC 6238 compliant.
"""
from __future__ import annotations

import pyotp

from app.config import get_settings

settings = get_settings()


def generate_totp_secret() -> str:
    """Generate a new base32-encoded TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Return the otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.totp_issuer_name)


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code against the stored secret.
    Allows ±1 interval (30 seconds) of drift.
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
