"""Regression tests for two real bugs found and fixed during cleanup:

1. `_handle_raw_frame` referenced `json.JSONDecodeError` without ever
   importing `json`, so any malformed WebSocket frame raised a bare
   `NameError` instead of the intended `InvalidPayloadError` -- which
   bypassed the reconnect logic entirely and killed the bot session.

2. `_event_worker` didn't isolate exceptions raised by a bot's own event
   handlers (on_chat, on_tip, etc). One buggy handler permanently took a
   worker out of the pool, silently shrinking capacity over time.
"""
import asyncio

import pytest

from highrise.configs import BotConfig
from highrise.core.bot_connection_manager import ConnectionManager
from highrise.errors import InvalidPayloadError
from highrise.tools.logger import setup_logger

auto_loop = pytest.mark.asyncio


class FakeBot:
    def __init__(self):
        self.config = BotConfig()
        self.logger = setup_logger(name="test", show_time=False)


@auto_loop
async def test_malformed_frame_raises_invalid_payload_not_nameerror():
    manager = ConnectionManager(bot=FakeBot())
    with pytest.raises(InvalidPayloadError):
        await manager._handle_raw_frame(b"{not valid json")


@auto_loop
async def test_event_worker_keeps_running_after_handler_exception():
    manager = ConnectionManager(bot=FakeBot())
    seen = []

    async def fake_dispatch(data):
        seen.append(data["_type"])
        if data["_type"] == "Boom":
            raise RuntimeError("simulated handler bug")

    manager._dispatch_events = fake_dispatch
    manager._event_queue = asyncio.Queue()
    manager._event_queue.put_nowait({"_type": "Boom"})
    manager._event_queue.put_nowait({"_type": "ChatEvent"})
    manager._event_queue.put_nowait(None)  # sentinel: stop the worker

    await manager._event_worker()

    # The worker must have processed the event *after* the one that raised.
    assert seen == ["Boom", "ChatEvent"]
