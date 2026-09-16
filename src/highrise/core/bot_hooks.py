import warnings
from typing import Any

from ..models.websocket.highrise_models import *


class BotHooks:
    """Default no-op implementations for all bot lifecycle and event hooks."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "on_voice_change" in cls.__dict__:
            warnings.warn(
                f"{cls.__name__} overrides 'on_voice_change', which was deprecated "
                "in Highrise update 4.25.3 and will not receive events.",
                DeprecationWarning,
                stacklevel=2,
            )

    async def before_start(self) -> None: pass
    async def on_start(self, session_metadata: SessionMetadata) -> None: pass
    async def on_reconnect(self, session_metadata: SessionMetadata) -> None: pass
    async def on_disconnect(self) -> None: pass
    async def on_chat(self, user: User, message: Message) -> None: pass
    async def on_whisper(self, user: User, message: Message) -> None: pass
    async def on_user_join(self, user: User, position: Position) -> None: pass
    async def on_user_leave(self, user: User) -> None: pass
    async def on_emote(self, user: User, emote_id: str, receiver: Receiver | None) -> None: pass
    async def on_reaction(self, user: User, reaction: Reaction, receiver: User) -> None: pass

    async def on_user_move(self, user: User, position: Position | None, anchor: AnchorPosition | None) -> None: pass
    async def on_tip(self, sender: Sender, receiver: Receiver, tip: CurrencyItem | Item) -> None: pass
    async def on_message(self, user_id: str, message: Message | None, conversation: Conversation) -> None: pass
    async def on_voice_change(self, users: list[Any], seconds_left: int) -> None: pass
    async def on_moderate(self, moderator_id: str, target_user_id: str, action: ModerationAction) -> None: pass
    async def on_channel(self, bot_id: str, message: str, tags: list[str]) -> None: pass
