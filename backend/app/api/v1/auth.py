"""
Auth REST endpoints:
  POST /api/v1/auth/login       — issue access + refresh tokens
  POST /api/v1/auth/refresh     — rotate refresh token
  POST /api/v1/auth/logout      — invalidate all user sessions
  GET  /api/v1/auth/me          — return current user profile
  POST /api/v1/auth/totp/setup  — generate TOTP QR
  POST /api/v1/auth/totp/verify — activate TOTP (persist to DB)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    revoke_all_user_tokens,
)
from app.auth.totp import generate_totp_secret, get_totp_uri, verify_totp_code
from app.dependencies import CurrentUser, DBSession
from app.models.user import User

router = APIRouter()


# ─── Request / Response schemas ───────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    totp_enabled: bool


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str


class TOTPVerifyRequest(BaseModel):
    secret: str
    totp_code: str


# ─── Routes ───────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession):
    """
    Authenticate user with email + password.
    If TOTP is enabled on the account, totp_code is also required.
    Returns short-lived access token and long-lived refresh token.
    """
    from app.auth.password import verify_password

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    # TOTP check if enabled
    if user.totp_secret:
        if not body.totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TOTP code required.",
            )
        if not verify_totp_code(user.totp_secret, body.totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code.",
            )

    claims = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(claims)
    refresh_token = await create_refresh_token(claims)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    """
    Rotate refresh token — old token is invalidated, new pair issued.
    Implements token family rotation to detect token theft.
    """
    payload = await decode_refresh_token(body.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )
    claims = {"sub": payload["sub"], "email": payload["email"], "role": payload["role"]}
    access_token = create_access_token(claims)
    new_refresh_token = await create_refresh_token(claims)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser):
    """Invalidate all refresh tokens for the current user."""
    await revoke_all_user_tokens(current_user["sub"])
    return None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser, db: DBSession):
    """Return the currently authenticated user's profile."""
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        totp_enabled=user.totp_secret is not None,
    )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def totp_setup(current_user: CurrentUser):
    """
    Generate a new TOTP secret for the authenticated user.
    Returns the secret and otpauth:// URI for QR code rendering.
    The secret is NOT yet saved — call /totp/verify to activate.
    """
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, current_user["email"])
    return TOTPSetupResponse(secret=secret, uri=uri)


@router.post("/totp/verify", status_code=status.HTTP_204_NO_CONTENT)
async def totp_verify(body: TOTPVerifyRequest, current_user: CurrentUser, db: DBSession):
    """
    Verify the provided TOTP code against the setup secret.
    On success, persists the secret to the user record, activating 2FA.
    """
    if not verify_totp_code(body.secret, body.totp_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code. Check your authenticator app time sync.",
        )
    await db.execute(
        update(User)
        .where(User.id == current_user["sub"])
        .values(totp_secret=body.secret)
    )
    await db.commit()
    return None
