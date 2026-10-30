"""Shows strict validation, the invalid-packet hook and a per-user cooldown.

Run:
    python -m highrise_fast examples.strict_bot:StrictBot ROOM_ID API_TOKEN
"""

from __future__ import annotations

import logging

from highrise_fast import BaseBot, HighriseFastValidationError

log = logging.getLogger("strict_bot")


class StrictBot(BaseBot):
    """Logs malformed packets instead of letting them reach handlers."""

    def __init__(self) -> None:
        super().__init__(
            validation_mode="strict",
            on_invalid="drop",
            invalid_warn_cooldown=30.0,
        )
        self._seen: set[str] = set()

    async def on_start(self, session_metadata) -> None:
        health = __import__("highrise_fast").health()
        log.info("started; sdk health: %s", health.get("status"))

    def on_invalid_packet(self, exc: Exception, raw: dict) -> None:
        """Called for every packet that fails validation (sync or async)."""
        if isinstance(exc, HighriseFastValidationError):
            # short() names the JSON path and the reason code.
            log.warning("dropped invalid packet: %s", exc.short())
        else:
            log.warning("dropped invalid packet: %r", exc)

    async def on_chat(self, user, message: str) -> None:
        if user.id in self._seen:
            return
        self._seen.add(user.id)
        await self.highrise.chat(f"first message from {user.username}, hello!")
