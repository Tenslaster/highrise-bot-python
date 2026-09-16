import inspect
from typing import Any
from collections.abc import Coroutine, Callable

from websockets import State

from .highrise_api import HighriseApi
from .constants import EVENT_HOOK_MAP
from .webapi import WebApi
from .configs import BotConfig

from .cache.room_users import RoomUsersCache

from .tools.logger import setup_logger
from .tools.awaiter import Awaiter
from .tools.roles import Roles

from .core.bot_ws_requester import WSRequester
from .core.bot_context import BotContext
from .core.bot_hooks import BotHooks
from .core.bot_connection_manager import ConnectionManager
from .core.bot_task_manager import TaskManager

from .models.websocket.highrise_models import *


class BaseBot(BotHooks):
    """A base class for Highrise bots.
        Bots join a room and interact with everything in it.

        Subclass this class and implement the handlers you want to use.

        The `self.highrise` attribute can be used to make requests.
    """

    def __init__(self, config: BotConfig | None = None) -> None:
        self.config = config or BotConfig()

        self.logger = setup_logger(
            name=self.config.logger.name,
            level=self.config.logger.level,
            show_time=self.config.logger.show_time,
        )

        requester = WSRequester(
            lambda: self._connection.ws_client,
            self.logger,
            default_timeout=self.config.connection.request_timeout,
            max_pending_requests=self.config.connection.max_pending_requests,
        )
        self._context = BotContext(requester)

        self.highrise = HighriseApi(self._context)
        self.cached_users = RoomUsersCache()
        self.awaiter = Awaiter()
        self.roles = Roles(path=self.config.roles.path)
        self.webapi = WebApi(self._context)

        self._connection = ConnectionManager(bot=self)
        self._tasks = TaskManager(bot=self)

        self._event_params = self._get_requested_events()

    def _get_requested_events(self) -> str:
        """Builds the WebSocket event subscription string by checking
        which hooks a subclass actually overrides, so the bot only
        subscribes to events it will actually handle."""
        active_events: set[str] = set()
        for event_name, hook_names in EVENT_HOOK_MAP.items():
            for hook in hook_names:
                subclass_method = getattr(self, hook, None)
                base_method = getattr(BaseBot, hook, None)
                subclass_func = getattr(subclass_method, "__func__", subclass_method)

                if inspect.unwrap(subclass_func) != inspect.unwrap(base_method):
                    active_events.add(event_name)
                    break
        return ",".join(active_events)

    # -- Public Methods

    async def login(self, room_id: str, api_token: str, auto_reconnect: bool = True) -> None:
        """Connects to the room and starts listening for events. Blocks
        until the bot stops running."""
        await self._connection.login(room_id, api_token, auto_reconnect)

    async def logout(self) -> None:
        """Gracefully disconnects and disables auto-reconnect."""
        await self._connection.logout()

    async def reconnect(self) -> None:
        """Forces a socket disconnect to trigger a fresh reconnect."""
        await self._connection.force_reconnect()

    def pause(self) -> bool:
        """Stops event dispatch without disconnecting. Returns True if
        the bot was not already paused."""
        return self._connection.pause()

    def resume(self) -> bool:
        """Resumes event dispatch after pause(). Returns True if the
        bot was actually paused."""
        return self._connection.resume()

    ## -- Decorators

    def loop(self, seconds: float):
        """Registers a function to run automatically on a repeating
        interval for as long as the bot is connected."""

        def decorator(func: Callable[[], Coroutine[Any, Any, None]] = None):
            self._tasks.register_loop(seconds, func)
            return func

        return decorator

    # -- Properties

    @property
    def session_metadata(self) -> "SessionMetadata | None":
        """The session metadata received once connected, or None before then."""
        return self._context.session_metadata

    @property
    def my_id(self) -> str | None:
        metadata = self.session_metadata
        return metadata.user_id if metadata is not None else None

    @property
    def bot_id(self) -> str | None:
        return self.my_id

    @property
    def bot_user_id(self) -> str | None:
        return self.my_id

    @property
    def user_id(self) -> str | None:
        return self.my_id

    @property
    def me(self) -> User | None:
        user_id = self.my_id
        if user_id is None:
            return None
        return User(id=user_id, username="")

    @property
    def state(self) -> State | None:
        """The raw WebSocket connection state, or None if not connected."""
        return self._connection.state

    @property
    def credentials(self) -> Credentials | None:
        """The room_id/api_token used for this session, or None before connecting."""
        return self._context.credentials

    @property
    def is_connected(self) -> bool:
        """True if the WebSocket connection is currently open."""
        return self._connection.is_connected

    @property
    def is_paused(self) -> bool:
        """True if event dispatch is currently paused."""
        return self._connection.is_paused

    @property
    def uptime(self) -> float:
        """Seconds since the current connection was established."""
        return self._context.metrics.uptime

    @property
    def latency(self) -> float | None:
        """Round-trip time in seconds of the last keepalive, or None."""
        return self._context.metrics.latency

    @property
    def events_processed(self) -> int:
        """Total events processed since the current connection was established."""
        return self._context.metrics.events_processed

    @property
    def lifetime_events_processed(self) -> int:
        """Total events processed across all connections since bot startup."""
        return self._context.metrics.lifetime_events_processed

    @property
    def lifetime_events_dropped(self) -> int:
        """Total events dropped across all connections since bot startup."""
        return self._context.metrics.lifetime_events_dropped

    @property
    def peak_latency(self) -> float | None:
        """Highest observed keepalive round-trip this session, or None."""
        return self._context.metrics.peak_latency
