"""High-throughput request/response correlation for the Highrise WebSocket."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(slots=True)
class PendingRequest:
    """Bookkeeping for one in-flight request."""

    future: asyncio.Future[tuple[bool, Any]]
    request_type: str


class WSRequester:
    """Request multiplexer with scoped IDs, cleanup, and serialized writes.

    Every terminal path removes a pending request. Writes are protected by one
    lock because several bot tasks may send at the same time.
    """

    __slots__ = (
        "_get_ws", "logger", "default_timeout", "max_pending_requests",
        "_pending_requests", "_ids", "_closed", "_session", "_write_lock",
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
        self._pending_requests: dict[str, PendingRequest] = {}
        self._ids = count()
        self._closed = False
        self._session = 0
        self._write_lock = asyncio.Lock()

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

        deadline = self.default_timeout if timeout is None else timeout
        if deadline <= 0:
            raise ValueError("timeout must be > 0")

        rid = f"{self._session:x}-{next(self._ids):x}"
        message = dict(payload)
        message["rid"] = rid
        future = asyncio.get_running_loop().create_future()
        request_type = str(message.get("_type", "UnknownRequest"))
        self._pending_requests[rid] = PendingRequest(future, request_type)

        try:
            # Serialize and send under the same lock. This prevents concurrent
            # writes from interleaving while retaining concurrent responses.
            async with self._write_lock:
                await ws.send(dumps(message))
            return await asyncio.wait_for(asyncio.shield(future), deadline)
        except asyncio.TimeoutError as exc:
            raise RequestTimeoutError(
                f"Request {rid} ({request_type}) timed out after {deadline:.2f}s"
            ) from exc
        except asyncio.CancelledError as exc:
            if not future.done():
                future.cancel()
            # Preserve asyncio cancellation semantics for shutdown. Callers
            # that explicitly need a request error can inspect task state.
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
        pending = self._pending_requests.get(rid)
        if pending is None or pending.future.done():
            return False
        if data.get("_type") == "Error":
            pending.future.set_result((False, data.get("message") or "Unknown server error."))
        else:
            pending.future.set_result((True, data))
        return True

    def close(self, reason: str = "Connection closed.") -> None:
        for pending in tuple(self._pending_requests.values()):
            if not pending.future.done():
                pending.future.set_result((False, reason))
        self._pending_requests.clear()

    def reopen(self) -> None:
        self.close("Session ended; requester reopening for new connection.")
        self._session += 1
        self._closed = False

    def shutdown(self) -> None:
        self._closed = True
        self.close("Requester shut down.")
