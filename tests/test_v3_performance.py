import asyncio

import pytest

from highrise.core.bot_ws_requester import WSRequester
from highrise.core.codec import dumps, loads
from highrise.errors import NotConnectedError, RequestCancelledError
from websockets import State


class FakeWS:
    state = State.OPEN

    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_ids_are_small_and_unique_per_session():
    ws = FakeWS()
    requester = WSRequester(lambda: ws, None, default_timeout=0.5)
    tasks = []

    async def answer(payload):
        data = loads(payload)
        requester.handle_incoming_response({"rid": data["rid"], "_type": "AcknowledgementResponse"})

    async def one():
        task = asyncio.create_task(requester.send({"_type": "X"}))
        while not ws.sent:
            await asyncio.sleep(0)
        payload = ws.sent.pop(0)
        await answer(payload)
        return await task

    for _ in range(100):
        tasks.append(asyncio.create_task(one()))
    results = await asyncio.gather(*tasks)
    assert all(ok for ok, _ in results)
    assert requester.pending_count == 0


@pytest.mark.asyncio
async def test_cancellation_is_clean():
    ws = FakeWS()
    requester = WSRequester(lambda: ws, None, default_timeout=5)
    task = asyncio.create_task(requester.send({"_type": "X"}))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(RequestCancelledError):
        await task
    assert requester.pending_count == 0


def test_codec_roundtrip():
    value = {"_type": "ChatRequest", "message": "héllo", "n": [1, 2, 3]}
    assert loads(dumps(value)) == value


@pytest.mark.asyncio
async def test_not_connected_is_fast_failure():
    requester = WSRequester(lambda: None, None)
    with pytest.raises(NotConnectedError):
        await requester.send({"_type": "X"})
