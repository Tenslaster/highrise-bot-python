# Highrise Bot Python SDK

Unofficial Python SDK for [Highrise Virtual Reality](https://highrise.game).

1:1 with the official SDK on every core method, plus a set of tools it
doesn't have: live room caching, uptime/latency/events_processed metrics,
background loops, a dynamic command system with role-based permissions,
local role persistence, auto message splitting, pause/resume, config-driven
setup, a public WebApi client, and pagination support across the board using
`async for-in` loops.

> **Coming from the official SDK?** A few event hooks changed shape and
> `Message` is now a class with helper methods (`.command()`, `.args()`,
> `.mentions()`) instead of a plain string.

See `CHANGELOG.md` for the version history, including the reliability and
performance work in this release.

## Installation

```bash
pip install -e .
```

## Quick start

```python
import asyncio
from highrise import BaseBot

class MyBot(BaseBot):
    async def on_chat(self, user, message):
        print(f"{user.username}: {message.content}")

if __name__ == "__main__":
    ROOM_ID = "put_your_room_id_here"
    API_TOKEN = "put_your_bot_token_here"

    bot = MyBot()

    try:
        asyncio.run(bot.login(ROOM_ID, API_TOKEN))
    except KeyboardInterrupt:
        print("\nBot stopped manually by user.")
```

`User`, `Position`, `AnchorPosition`, `Message`, `Sender`, `Receiver`,
`Conversation`, `Item`, `CurrencyItem`, `ModerationAction`, `Credentials`,
`SessionMetadata`, `RoomInfo`, `OutfitItem`, and `RoomPermissions` are all
importable directly from `highrise`, e.g. `from highrise import User`.

## Reliability & performance architecture

The SDK separates persistent bot state from connection-scoped state and has:

- Per-instance WebSocket request correlation with deadlines and guaranteed cleanup.
- Bounded event queues with a configurable worker pool; a single event
  handler raising an exception is logged and isolated, not fatal to the
  worker that hit it.
- WebSocket message / receive-queue limits.
- Reconnection backoff with jitter.
- Explicit lifecycle cleanup for WebSocket, tasks, loops, and HTTP resources.
- Defensive JSON payload validation and typed SDK exceptions.
- Validated role-file loading and safer awaiter argument checks.
- `slots=True` on the model classes built for every incoming event (`User`,
  `Position`, `Message`, etc.) for lower per-object memory and faster
  attribute access on the hot path.

Example configuration:

```python
from highrise import BaseBot, BotConfig, ConnectionConfig

config = BotConfig(
    connection=ConnectionConfig(
        request_timeout=10,
        event_queue_size=1000,
        event_workers=8,
        max_message_size=1_048_576,
        websocket_max_queue=64,
        reconnect_jitter=0.25,
    )
)

bot = BaseBot(config)
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
