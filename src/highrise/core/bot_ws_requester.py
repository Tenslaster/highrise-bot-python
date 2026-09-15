"""High-throughput request/response correlation for the Highrise WebSocket."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from itertools import count
from typing import Any

from websockets import ClientConnection, State

from ..errors import (
    ConnectionLostError,
    NotConnectedError,
    RequestCapacityError,
    RequestCancelledError,
    RequestTimeoutError,
)
from .codec import dumps


class WSRequester:
    """Low-overhead request multiplexer.

    One Future represents exactly one request. Pending requests are scoped to
    this requester instance, and every terminal path removes its registry entry.
    """

    __slots__ = (
        "_get_ws", "logger", "default_timeout", "max_pending_requests",
        "_pending_requests", "_ids", "_closed", "_session", "_lock",
    )

    def __init__(
        self,
        ws_getter: Callable[[], ClientConnection | None],
        logger,
        *,
        default_timeout: float = 10.0,
        max_pending_requests: int = 256,
    ) -> None:
        if default_timeout <= 0:
            raise ValueError("default_timeout must be > 0")
        if max_pending_requests <= 0:
            raise ValueError("max_pending_requests must be > 0")
        self._get_ws = ws_getter
        self.logger = logger
        self.default_timeout = default_timeout
        self.max_pending_requests = max_pending_requests
        self._pending_requests: dict[str, asyncio.Future[tuple[bool, Any]]] = {}
        self._ids = count()
        self._closed = False
        self._session = 0
        self._lock = asyncio.Lock()

    @property
    def pending_count(self) -> int:
        return len(self._pending_requests)

    async def send(self, payload: dict[str, Any], timeout: float | None = None) -> tuple[bool, Any]:
        if self._closed:
            raise NotConnectedError("Requester is closed.")

        ws = self._get_ws()
        if ws is None or ws.state != State.OPEN:
            raise NotConnectedError("WebSocket is not connected.")

        if len(self._pending_requests) >= self.max_pending_requests:
            raise RequestCapacityError(
                f"Maximum pending requests reached ({self.max_pending_requests})."
            )

        rid = f"{self._session:x}-{next(self._ids):x}"
        message = dict(payload)
        message["rid"] = rid
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[rid] = future
        deadline = self.default_timeout if timeout is None else timeout
        if deadline <= 0:
            self._pending_requests.pop(rid, None)
            raise ValueError("timeout must be > 0")

        try:
            await ws.send(dumps(message))
            return await asyncio.wait_for(asyncio.shield(future), deadline)
        except asyncio.TimeoutError as exc:
            raise RequestTimeoutError(
                f"Request {rid} timed out after {deadline:.2f}s"
            ) from exc
        except asyncio.CancelledError as exc:
            if not future.done():
                future.cancel()
            raise RequestCancelledError(f"Request {rid} was cancelled.") from exc
        except (ConnectionError, OSError) as exc:
            raise ConnectionLostError(
                f"Connection lost while sending {rid}: {exc}"
            ) from exc
        finally:
            self._pending_requests.pop(rid, None)

    def handle_incoming_response(self, data: dict[str, Any]) -> bool:
        rid = data.get("rid")
        if not isinstance(rid, str):
            return False
        future = self._pending_requests.get(rid)
        if future is None or future.done():
            return False
        if data.get("_type") == "Error":
            future.set_result((False, data.get("message") or "Unknown server error."))
        else:
            future.set_result((True, data))
        return True

    def close(self, reason: str = "Connection closed.") -> None:
        for future in tuple(self._pending_requests.values()):
            if not future.done():
                future.set_result((False, reason))
        self._pending_requests.clear()

    def reopen(self) -> None:
        self._session += 1
        self._closed = False

    def shutdown(self) -> None:
        self._closed = True
        self.close("Requester shut down.")
