"""Runs an official-SDK bot unchanged by installing the `highrise` alias.

This demonstrates the drop-in path: the bot below imports from ``highrise``,
exactly like one written against the official SDK. The alias is installed
first, so those imports resolve to highrise_fast.

Run:
    python examples/alias_migration.py ROOM_ID API_TOKEN
"""

from __future__ import annotations

import asyncio
import sys

import highrise_fast

# Must happen before anything imports `highrise`.
highrise_fast.install_alias()

from highrise import BaseBot  # noqa: E402  (resolved to highrise_fast)

print("alias active:", highrise_fast.alias_active())
print("BaseBot is highrise_fast.BaseBot:", BaseBot is highrise_fast.BaseBot)


class OfficialStyleBot(BaseBot):
    """Written against the official SDK, runs unmodified."""

    async def on_chat(self, user, message: str) -> None:
        if message.lower() == "!ping":
            await self.highrise.chat("pong from the alias")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    room_id, token = sys.argv[1], sys.argv[2]
    asyncio.run(highrise_fast.bot_runner(OfficialStyleBot(), room_id, token))
