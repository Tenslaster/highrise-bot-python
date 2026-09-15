from typing import Any

from ..models.websocket.highrise_models import *

class BotHooks:
    """Default no-op implementations for all bot lifecycle and event hooks.

    Subclass BaseBot and override the hooks you want to use.
    """

    async def before_start(self) -> None:
        """Called once before the bot attempts to connect, prior to any login or reconnect attempts."""
        pass

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        """Lifecycle hook called once the bot has successfully connected."""
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

        - `Maybe Deprecated`
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

        - `Deprecated in update 4.25.3`
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