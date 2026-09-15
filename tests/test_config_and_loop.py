import asyncio
import pytest

from highrise.configs import ConnectionConfig
from highrise.tools.loop_task import LoopTask


def test_connection_config_rejects_bad_queue():
    with pytest.raises(ValueError):
        ConnectionConfig(event_queue_size=0)


def test_connection_config_rejects_bad_jitter():
    with pytest.raises(ValueError):
        ConnectionConfig(reconnect_jitter=1.1)


@pytest.mark.asyncio
async def test_loop_task_cancels_cleanly():
    calls = 0

    async def work():
        nonlocal calls
        calls += 1

    loop = LoopTask(work, seconds=0.01)
    loop.start()
    await asyncio.sleep(0.03)
    await loop.cancel()

    assert calls >= 1
    assert loop.get_loop_task is None
