import asyncio
import json

import pytest

from highrise.core.bot_ws_requester import WSRequester
from highrise.errors import RequestTimeoutError


class FakeWS:
    def __init__(self):
        self.state = type("State", (), {"name": "OPEN"})()
        self.sent = []

    async def send(self, payload):
        self.sent.append(payload)


auto_loop = pytest.mark.asyncio


@auto_loop
async def test_request_is_correlated_and_cleaned_up():
    ws = FakeWS()
    # Patch the exact state object expected by the requester.
    from websockets import State
    ws.state = State.OPEN
    requester = WSRequester(lambda: ws, logger=None, default_timeout=0.2)

    async def responder():
        while not ws.sent:
            await asyncio.sleep(0)
        payload = json.loads(ws.sent[0])
        requester.handle_incoming_response({"_type": "AcknowledgementResponse", "rid": payload["rid"]})

    responder_task = asyncio.create_task(responder())
    result = await requester.send({"_type": "ChatRequest", "message": "hello"})
    await responder_task

    assert result[0] is True
    assert requester.pending_count == 0


@auto_loop
async def test_timeout_cleans_registry():
    from websockets import State
    ws = FakeWS()
    ws.state = State.OPEN
    requester = WSRequester(lambda: ws, logger=None, default_timeout=0.01)

    with pytest.raises(RequestTimeoutError):
        await requester.send({"_type": "Test"})

    assert requester.pending_count == 0
