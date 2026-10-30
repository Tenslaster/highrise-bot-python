"""Minimal command bot.

Run:
    python -m highrise_fast examples.ping_bot:PingBot ROOM_ID API_TOKEN
"""

from __future__ import annotations

from highrise_fast import BaseBot, User


class PingBot(BaseBot):
    """Replies to a handful of chat commands."""

    async def on_start(self, session_metadata) -> None:
        room = session_metadata.room_info.room_name
        print(f"connected to {room} as {session_metadata.user_id}")

    async def on_chat(self, user: User, message: str) -> None:
        text = message.strip()
        if not text.startswith("!"):
            return

        command, _, argument = text.partition(" ")
        match command.lower():
            case "!ping":
                await self.highrise.chat("pong!")
            case "!whoami":
                await self.highrise.chat(f"you are {user.username} ({user.id})")
            case "!where":
                position = self.room_tracker.get_position(user.id)
                await self.highrise.chat(f"you are at {position}")
            case "!users":
                await self.highrise.chat(f"{self.room_tracker.user_count} in room")
            case "!echo":
                await self.highrise.chat(argument or "...")
            case _:
                await self.highrise.send_whisper(user.id, f"unknown command {command}")
