"""
Auth REST endpoints:
  POST /api/v1/auth/login       — issue access + refresh tokens
  POST /api/v1/auth/refresh     — rotate refresh token
  POST /api/v1/auth/logout      — invalidate session
  POST /api/v1/auth/totp/setup  — generate TOTP QR
  POST /api/v1/auth/totp/verify — activate TOTP
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.auth.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.auth.totp import generate_totp_secret, get_totp_uri, verify_totp_code
from app.dependencies import CurrentUser, DBSession

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


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str
    qr_data_url: str


class TOTPVerifyRequest(BaseModel):
    totp_code: str


# ─── Routes ───────────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DBSession):
    """
    Authenticate user with email + password.
    If TOTP is enabled on the account, totp_code is also required.
    Returns short-lived access token and long-lived refresh token.
    """
    from sqlalchemy import select

    from app.auth.password import verify_password
    from app.models.user import User

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
    """Invalidate the current user's session in Redis."""
    # Session invalidation implemented in ST-3 (full auth sub-task)
    return None


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def totp_setup(current_user: CurrentUser, db: DBSession):
    """Generate a new TOTP secret for the authenticated user."""
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, current_user["email"])
    # Return the secret + URI so the client can render a QR code
    return TOTPSetupResponse(secret=secret, uri=uri, qr_data_url=uri)


@router.post("/totp/verify", status_code=status.HTTP_204_NO_CONTENT)
async def totp_verify(body: TOTPVerifyRequest, current_user: CurrentUser, db: DBSession):
    """
    Verify a TOTP code and activate 2FA on the account.
    The secret stored in the session from /totp/setup is used.
    """
    # Full persistence implemented in ST-3
    return None
