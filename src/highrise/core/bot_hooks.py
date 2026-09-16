import warnings
from typing import Any

from ..models.websocket.highrise_models import *


class BotHooks:
    """Default no-op implementations for all bot lifecycle and event hooks.

    Subclass BaseBot and override the hooks you want to use.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Warn at class-definition time if a subclass overrides a deprecated hook.
        if "on_voice_change" in cls.__dict__:
            warnings.warn(
                f"{cls.__name__} overrides 'on_voice_change', which was deprecated "
                "in Highrise update 4.25.3 and will not receive events. "
                "Remove the override to suppress this warning.",
                DeprecationWarning,
                stacklevel=2,
            )

    async def before_start(self) -> None:
        """Called once before the bot attempts to connect, prior to any login or reconnect attempts."""
        pass

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        """Lifecycle hook called once the bot has successfully connected.

        This fires on the *first* connection and on every successful reconnect.
        Use ``on_reconnect`` if you only want to react to reconnects after
        the initial login.
        """
        pass

    async def on_reconnect(self, session_metadata: SessionMetadata) -> None:
        """Called after each successful reconnect (not on the first connect).

        Override this to re-sync room state, re-teleport the bot, or clear
        any connection-scoped caches after a reconnect.
        """
        pass

    async def on_disconnect(self) -> None:
        """Called when the WebSocket connection is lost before a reconnect attempt.

        Override this to react to drops — e.g. log the disconnect, cancel
        timers, or notify an external monitoring system.
        """
        pass

    async def on_chat(self, user: User, message: Message) -> None:
        """Called when a user sends a message in the room."""
        pass

    async def on_whisper(self, user: User, message: Message) -> None:
        """Called when the bot receives a private whisper."""
        pass

    async def on_user_join(self, user: User, position: Position) -> None:
        """Called when a user enters the room."""
        pass

    async def on_user_leave(self, user: User) -> None:
        """Called when a user leaves the room."""
        pass

    async def on_emote(self, user: User, emote_id: str, receiver: Receiver) -> None:
        """Called when a user performs an emote.

        .. note::
            This event may be deprecated by Highrise in a future update.
        """
        pass

    async def on_user_move(
        self,
        user: User,
        position: Position | None,
        anchor: AnchorPosition | None,
    ) -> None:
        """Called when a user moves or changes position in the room."""
        pass

    async def on_tip(self, sender: Sender, receiver: Receiver, tip: CurrencyItem) -> None:
        """Called when a tip (currency) is exchanged between two players."""
        pass

    async def on_message(
        self, user_id: str, message: Message | None, conversation: Conversation
    ) -> None:
        """Called when the bot receives a Direct Message (DM).

        `message` is `None` unless `auto_fetch.direct_message` is enabled
        in `BotConfig`, since fetching the message content requires an
        extra API call. Enable it via:

        ```
        config = BotConfig(auto_fetch=AutoFetchConfig(direct_message=True))
        bot = MyBot(config)
        ```
        """
        pass

    async def on_voice_change(self, users: list[Any], seconds_left: int) -> None:
        """Called when there is an update to the room's voice status.

        .. deprecated::
            Deprecated in Highrise update 4.25.3. Overriding this hook will
            emit a ``DeprecationWarning`` at class-definition time.
        """
        pass

    async def on_moderate(
        self,
        moderator_id: str,
        target_user_id: str,
        action: ModerationAction,
    ) -> None:
        """Called when a moderation action occurs in the room."""
        pass

    async def on_channel(self, bot_id: str, message: str, tags: list[str]) -> None:
        """Called when a message is received on the hidden channel."""
        pass