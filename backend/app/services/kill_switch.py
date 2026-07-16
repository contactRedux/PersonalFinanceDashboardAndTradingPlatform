"""
Kill-switch service — platform-wide order submission gate.

Uses Redis as the backing store so the flag is shared across all
API worker processes and survives server restarts.

Key:   `kill_switch:orders`
Value: "1" = active (orders blocked), absent = inactive (orders allowed)
"""

from __future__ import annotations

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_REDIS_KEY = "kill_switch:orders"


class KillSwitch:
    """
    Thin wrapper around Redis for the kill-switch flag.

    A new Redis connection is opened on first use so the class can be
    instantiated at module level without requiring a running Redis.
    """

    def __init__(self) -> None:
        self._redis: object | None = None

    async def _get_redis(self):  # type: ignore[return]
        """Return a shared redis.asyncio.Redis client (lazy init)."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis  # noqa: PLC0415

                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            except Exception:  # noqa: BLE001
                logger.warning("kill_switch.redis_unavailable")
                return None
        return self._redis

    async def is_active(self) -> bool:
        """Return True when the kill-switch is engaged (orders blocked)."""
        r = await self._get_redis()
        if r is None:
            return False  # fail-open: if Redis is down, don't block orders
        try:
            val = await r.get(_REDIS_KEY)
            return val == "1"
        except Exception:  # noqa: BLE001
            logger.warning("kill_switch.redis_read_error")
            return False

    async def enable(self) -> None:
        """Engage the kill-switch — block all new order submissions."""
        r = await self._get_redis()
        if r is None:
            logger.error("kill_switch.enable.redis_unavailable")
            return
        await r.set(_REDIS_KEY, "1")
        logger.warning("kill_switch.enabled")

    async def disable(self) -> None:
        """Disengage the kill-switch — restore order submissions."""
        r = await self._get_redis()
        if r is None:
            logger.error("kill_switch.disable.redis_unavailable")
            return
        await r.delete(_REDIS_KEY)
        logger.info("kill_switch.disabled")
