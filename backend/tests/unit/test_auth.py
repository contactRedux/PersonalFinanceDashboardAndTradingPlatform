"""
Unit tests for JWT auth utilities.
"""
from __future__ import annotations

from app.auth.jwt import create_access_token, decode_access_token
from app.auth.password import hash_password, verify_password
from app.auth.rbac import has_role
from app.auth.totp import generate_totp_secret, verify_totp_code


# ─── JWT ──────────────────────────────────────────────────────────────────────
def test_create_and_decode_access_token():
    claims = {"sub": "user-123", "email": "test@example.com", "role": "trader"}
    token = create_access_token(claims)
    assert isinstance(token, str)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["role"] == "trader"
    assert payload["type"] == "access"


def test_decode_invalid_token_returns_none():
    assert decode_access_token("not.a.valid.token") is None


def test_decode_tampered_token_returns_none():
    claims = {"sub": "user-123", "email": "test@example.com", "role": "trader"}
    token = create_access_token(claims)
    tampered = token[:-5] + "XXXXX"
    assert decode_access_token(tampered) is None


# ─── Password hashing ─────────────────────────────────────────────────────────
def test_hash_and_verify_password():
    plain = "SuperSecureP@ssw0rd!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)


def test_wrong_password_fails_verification():
    hashed = hash_password("correct-password")
    assert not verify_password("wrong-password", hashed)


# ─── TOTP ─────────────────────────────────────────────────────────────────────
def test_generate_totp_secret_is_valid_base32():
    secret = generate_totp_secret()
    assert len(secret) >= 16
    # base32 alphabet: A-Z and 2-7
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in secret)


def test_verify_totp_with_current_code():
    import pyotp
    secret = generate_totp_secret()
    totp = pyotp.TOTP(secret)
    current_code = totp.now()
    assert verify_totp_code(secret, current_code)


def test_verify_totp_wrong_code_fails():
    secret = generate_totp_secret()
    assert not verify_totp_code(secret, "000000")


# ─── RBAC ─────────────────────────────────────────────────────────────────────
def test_admin_has_all_roles():
    assert has_role("admin", "admin")
    assert has_role("admin", "trader")
    assert has_role("admin", "analyst")
    assert has_role("admin", "readonly")


def test_readonly_cannot_elevate():
    assert has_role("readonly", "readonly")
    assert not has_role("readonly", "analyst")
    assert not has_role("readonly", "trader")
    assert not has_role("readonly", "admin")


def test_trader_can_analyst_and_readonly():
    assert has_role("trader", "analyst")
    assert has_role("trader", "readonly")
    assert not has_role("trader", "admin")
