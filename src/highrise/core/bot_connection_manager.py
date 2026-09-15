from __future__ import annotations

import asyncio
import random
import websockets
from typing import Any, TYPE_CHECKING

from websockets import State
from websockets.asyncio.client import connect

from ..constants import HIGHRISE_WS_URI, SERVER_ERRORS
from ..errors import InvalidPayloadError
from .codec import loads
from ..models.websocket.highrise_models import Credentials
from .bot_event_handlers import EVENT_HANDLERS

if TYPE_CHECKING:
    from ..base_bot import BaseBot


class ConnectionManager:
    """Owns connection lifecycle, bounded event dispatch, and reconnects."""

    def __init__(self, bot: "BaseBot") -> None:
        self.bot = bot
        self._ws: websockets.ClientConnection | None = None
        self._is_running = False
        self._is_paused = False
        self._auto_reconnect = True
        self._login_started = False
        self._shutdown_lock = asyncio.Lock()
        self._session_generation = 0
        self._event_queue: asyncio.Queue[dict[str, Any] | None] | None = None
        self._event_workers: list[asyncio.Task[Any]] = []

        cfg = bot.config.connection
        self._cfg = cfg

    @property
    def ws_client(self) -> websockets.ClientConnection | None:
        return self._ws

    @property
    def state(self) -> State | None:
        return self._ws.state if self._ws is not None else None

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._ws.state == State.OPEN

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    async def login(self, room_id: str, api_token: str, auto_reconnect: bool = True) -> None:
        if not isinstance(room_id, str) or not room_id.strip():
            raise ValueError("room_id must be a non-empty string")
        if not isinstance(api_token, str) or not api_token.strip():
            raise ValueError("api_token must be a non-empty string")
        if self._login_started and self._is_running:
            raise RuntimeError("Bot is already running")

        self._login_started = True
        self._is_running = True
        self._auto_reconnect = auto_reconnect
        self.bot._context.credentials = Credentials(room_id.strip(), api_token.strip())
        self.bot._tasks.on_first_start()

        try:
            self.bot.webapi.reopen()
            await self.bot.before_start()
            delay = self._cfg.min_reconnect_delay
            attempts = 0

            while self._is_running:
                try:
                    await self._connect_and_listen()
                    delay = self._cfg.min_reconnect_delay
                    attempts = 0
                except asyncio.CancelledError:
                    raise
                except (websockets.exceptions.ConnectionClosed, ConnectionError, OSError, TimeoutError) as exc:
                    if not self._should_reconnect():
                        break
                    attempts += 1
                    if self._exceeded_attempts(attempts):
                        break
                    wait = self._next_delay(delay)
                    self.bot.logger.warning(
                        "Connection lost (%s). Reconnecting in %.1fs...",
                        self._describe_connection_error(exc),
                        wait,
                    )
                    await asyncio.sleep(wait)
                    delay = min(delay * self._cfg.reconnect_backoff_factor, self._cfg.max_reconnect_delay)
                except InvalidPayloadError as exc:
                    self.bot.logger.error("Invalid server payload: %s", exc)
                    if not self._should_reconnect():
                        break
                    attempts += 1
                    if self._exceeded_attempts(attempts):
                        break
                    await asyncio.sleep(self._next_delay(delay))
                    delay = min(delay * self._cfg.reconnect_backoff_factor, self._cfg.max_reconnect_delay)
                except Exception as exc:
                    # Programming errors shouldn't be silently disguised as network failures.
                    self.bot.logger.exception("Unexpected error in connection loop: %s", exc)
                    break
                finally:
                    await self._cleanup_connection()
        finally:
            self._is_running = False
            self._login_started = False
            self.bot._context.requester.close("Connection loop ended.")
            await self.bot._tasks.shutdown()
            await self.bot.webapi.aclose()
            self.bot.logger.info("Bot session ended.")

    async def logout(self, hide_logs: bool = False) -> None:
        if not hide_logs:
            self.bot.logger.info("Logging out from Highrise Server...")
        self._is_running = False
        self._auto_reconnect = False
        await self._cleanup_connection()
        if not self._login_started:
            await self.bot._tasks.shutdown()
            await self.bot.webapi.aclose()
        if not hide_logs:
            self.bot.logger.info("Logged out successfully.")

    async def force_reconnect(self) -> None:
        if not self._is_running:
            self.bot.logger.warning("Cannot reconnect: Bot is not currently running.")
            return
        await self._cleanup_connection()

    def pause(self) -> bool:
        if self._is_paused:
            return False
        self._is_paused = True
        return True

    def resume(self) -> bool:
        if not self._is_paused:
            return False
        self._is_paused = False
        return True

    async def _connect_and_listen(self) -> None:
        await self._cleanup_connection()
        self._session_generation += 1
        self.bot._context.requester.reopen()

        credentials = self.bot.credentials
        if credentials is None:
            raise RuntimeError("Bot credentials are unavailable")

        headers = {
            "room-id": credentials.room_id,
            "api-token": credentials.api_token,
        }
        url = f"{HIGHRISE_WS_URI}?events={self.bot._event_params}"

        self._ws = await connect(
            url,
            additional_headers=headers,
            compression=None,
            open_timeout=self._cfg.open_timeout,
            close_timeout=self._cfg.close_timeout,
            ping_interval=None,
            max_size=self._cfg.max_message_size,
            max_queue=(self._cfg.websocket_max_queue, max(1, self._cfg.websocket_max_queue // 4)),
            write_limit=self._cfg.websocket_write_limit,
            user_agent_header=None,
        )
        self.bot._context.metrics.mark_connected()
        self._start_event_workers()

        if self.bot.config.auto_fetch.room_users:
            self.bot._tasks.create_task(self.bot._tasks.fetch_room_users(), name="fetch_room_users")

        self.bot._tasks.create_task(self._send_keepalive(), name="keepalive")
        self.bot._tasks.start_all_loops()

        while self._is_running and self.is_connected:
            raw_frame = await self._ws.recv()
            await self._handle_raw_frame(raw_frame)

    def _start_event_workers(self) -> None:
        self._event_queue = asyncio.Queue(maxsize=self._cfg.event_queue_size)
        self._event_workers.clear()
        for index in range(self._cfg.event_workers):
            self._event_workers.append(
                self.bot._tasks.create_task(
                    self._event_worker(),
                    name=f"event_worker_{index + 1}",
                )
            )

    async def _event_worker(self) -> None:
        queue = self._event_queue
        if queue is None:
            return
        while True:
            data = await queue.get()
            try:
                if data is None:
                    return
                if self._is_paused:
                    continue
                await self._dispatch_events(data)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # A single faulty event handler must not permanently take a
                # worker out of the pool: log it and keep processing events.
                self.bot.logger.error(
                    "Unhandled error while dispatching event %r: %s",
                    data.get("_type") if isinstance(data, dict) else type(data).__name__,
                    exc,
                    exc_info=True,
                )
            finally:
                queue.task_done()

    async def _send_keepalive(self) -> None:
        try:
            while self._is_running and self.is_connected:
                await asyncio.sleep(self._cfg.keepalive_delay)
                if not self.is_connected:
                    continue
                start = asyncio.get_running_loop().time()
                success, _ = await self.bot._context.requester.send(
                    {"_type": "KeepaliveRequest"},
                    timeout=min(self._cfg.request_timeout, self._cfg.keepalive_delay),
                )
                if success:
                    self.bot._context.metrics.record_latency(asyncio.get_running_loop().time() - start)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.bot.logger.debug("Keepalive loop stopped: %s", exc)

    async def _handle_raw_frame(self, raw_frame: str | bytes) -> None:
        try:
            if isinstance(raw_frame, bytes):
                raw_frame = raw_frame.decode("utf-8")
            data = loads(raw_frame)
        except (UnicodeDecodeError, ValueError) as exc:
            # Covers both stdlib json.JSONDecodeError and orjson.JSONDecodeError
            # (both are ValueError subclasses) without a hard dependency on
            # whichever codec is active. `json` was never imported here, so
            # referencing json.JSONDecodeError directly raised a NameError on
            # every malformed frame instead of triggering a clean reconnect.
            raise InvalidPayloadError(f"Invalid JSON frame: {exc}") from exc

        if not isinstance(data, dict):
            raise InvalidPayloadError("Incoming WebSocket payload must be a JSON object")

        data_message = data.get("message")
        if data_message in SERVER_ERRORS:
            await self._handle_server_errors(data)
            return

        if self.bot._context.requester.handle_incoming_response(data):
            return

        if self._is_paused:
            return

        if data.get("_type") == "KeepAliveResponse":
            return

        queue = self._event_queue
        if queue is None:
            return

        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            self.bot._context.metrics.record_dropped_event()
            self.bot.logger.warning(
                "Event queue full (%d); dropping incoming event type=%r",
                self._cfg.event_queue_size,
                data.get("_type"),
            )

    async def _dispatch_events(self, data: dict[str, Any]) -> None:
        event_type = data.get("_type")
        handler = EVENT_HANDLERS.get(event_type)
        if handler is None:
            self.bot.logger.debug("Ignoring unknown event type %r", event_type)
            return
        self.bot._context.metrics.record_event()
        await handler(self.bot, data)

    async def _cleanup_connection(self) -> None:
        async with self._shutdown_lock:
            self.bot._context.requester.close("Connection closed.")
            ws = self._ws
            self._ws = None

            queue = self._event_queue
            self._event_queue = None
            if queue is not None:
                for _ in self._event_workers:
                    try:
                        queue.put_nowait(None)
                    except asyncio.QueueFull:
                        break

            if ws is not None:
                try:
                    await ws.close()
                except Exception as exc:
                    self.bot.logger.debug("WebSocket close failed: %s", exc)
                finally:
                    self.bot._context.metrics.mark_disconnected()

            await self.bot._tasks.cancel_connection_tasks()
            self._event_workers.clear()
            self.bot._context.cache.clear_all()
            self.bot.cached_users.clear()

    async def _handle_server_errors(self, error_data: dict[str, Any]) -> None:
        error_message = str(error_data.get("message") or "Unknown server error occurred.")
        self.bot.logger.critical(error_message)
        self._is_running = False
        self._auto_reconnect = False

    def _should_reconnect(self) -> bool:
        return self._is_running and self._auto_reconnect

    def _exceeded_attempts(self, attempts: int) -> bool:
        limit = self._cfg.max_reconnect_attempts
        if limit is None:
            return False
        if attempts <= limit:
            return False
        self.bot.logger.warning("Max reconnect attempts (%d) reached. Giving up.", limit)
        return True

    def _next_delay(self, base: float) -> float:
        if self._cfg.reconnect_jitter == 0:
            return base
        spread = base * self._cfg.reconnect_jitter
        return max(0.0, base + random.uniform(-spread, spread))

    @staticmethod
    def _describe_connection_error(exc: BaseException) -> str:
        code = getattr(exc, "code", None)
        reason = getattr(exc, "reason", None)
        if code is not None:
            return f"code={code} reason={reason or 'n/a'}"
        return str(exc) or type(exc).__name__
