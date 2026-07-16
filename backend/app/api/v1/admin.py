"""
Admin API — platform-wide controls.

Endpoints:
  GET    /api/v1/admin/kill-switch          — get kill-switch state
  POST   /api/v1/admin/kill-switch/enable   — engage kill-switch (halts all order submissions)
  POST   /api/v1/admin/kill-switch/disable  — disengage kill-switch (restores order submissions)

Access: Restricted to users whose email appears in the ADMIN_EMAILS config list.

Kill-switch state is stored in Redis under key `kill_switch:orders` with value "1" (active) or
absent (inactive). This makes it instantly visible to every API worker without a DB round-trip and
survives process restarts as long as Redis is up.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.dependencies import CurrentUser
from app.services.kill_switch import KillSwitch

logger = structlog.get_logger(__name__)
router = APIRouter()
settings = get_settings()

_kill_switch = KillSwitch()


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _require_admin(current_user: dict) -> None:
    """Raise 403 if the current user is not in the ADMIN_EMAILS list."""
    admin_emails = settings.admin_emails
    user_email = current_user.get("email", "")
    if admin_emails and user_email not in admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )


# ─── Schemas ──────────────────────────────────────────────────────────────────


class KillSwitchStatus(BaseModel):
    active: bool
    message: str


# ─── Routes ───────────────────────────────────────────────────────────────────


@router.get("/kill-switch", response_model=KillSwitchStatus)
async def get_kill_switch_status(current_user: CurrentUser):
    """Return the current kill-switch state."""
    _require_admin(current_user)
    active = await _kill_switch.is_active()
    return KillSwitchStatus(
        active=active,
        message="Order submissions HALTED — kill-switch is active." if active
        else "Order submissions enabled — kill-switch is inactive.",
    )


@router.post("/kill-switch/enable", response_model=KillSwitchStatus)
async def enable_kill_switch(current_user: CurrentUser):
    """
    Engage the platform-wide kill-switch.

    All subsequent POST /orders and POST /orders/forex requests will be
    rejected with 503 until the kill-switch is disabled.
    """
    _require_admin(current_user)
    await _kill_switch.enable()
    logger.warning(
        "kill_switch.enabled",
        user_id=current_user.get("sub"),
        email=current_user.get("email"),
    )
    return KillSwitchStatus(active=True, message="Kill-switch ENABLED — all order submissions halted.")


@router.post("/kill-switch/disable", response_model=KillSwitchStatus)
async def disable_kill_switch(current_user: CurrentUser):
    """
    Disengage the platform-wide kill-switch.

    Order submissions resume immediately after this call.
    """
    _require_admin(current_user)
    await _kill_switch.disable()
    logger.info(
        "kill_switch.disabled",
        user_id=current_user.get("sub"),
        email=current_user.get("email"),
    )
    return KillSwitchStatus(active=False, message="Kill-switch DISABLED — order submissions restored.")
