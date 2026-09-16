from __future__ import annotations

from typing import Any, TYPE_CHECKING
from collections.abc import Callable

from .errors import HighriseError
from .compatibility import CompatibilityMixin
from .mixins.highrise.chat import ChatMixin
from .mixins.highrise.direct import DirectMixin
from .mixins.highrise.channel import ChannelMixin
from .mixins.highrise.player import PlayerMixin
from .mixins.highrise.room import RoomMixin
from .mixins.highrise.voice import VoiceMixin
from .mixins.highrise.wallet import WalletMixin
from .mixins.highrise.inventory import InventoryMixin
from .mixins.highrise.outfit import OutfitMixin

if TYPE_CHECKING:
    from .core.bot_context import BotContext


class HighriseApi(
    CompatibilityMixin,
    ChatMixin,
    DirectMixin,
    ChannelMixin,
    PlayerMixin,
    RoomMixin,
    VoiceMixin,
    WalletMixin,
    InventoryMixin,
    OutfitMixin,
):
    def __init__(self, context: "BotContext") -> None:
        self._context = context

    @property
    def bot_id(self) -> str | None:
        metadata = self._context.session_metadata
        return metadata.user_id if metadata is not None else None

    @property
    def bot_user_id(self) -> str | None:
        return self.bot_id

    @property
    def user_id(self) -> str | None:
        return self.bot_id

    @property
    def my_id(self) -> str | None:
        return self.bot_id

    @property
    def room_id(self) -> str | None:
        credentials = self._context.credentials
        return credentials.room_id if credentials is not None else None

    @property
    def me(self):
        from .models.websocket.highrise_models import User
        return User(self.bot_id, "") if self.bot_id else None

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any:
        payload = build_payload()
        try:
            success, data = await self._context.requester.send(
                payload, timeout=self._context.requester.default_timeout,
            )
            return response_cls._from_raw(success, data)
        except (ValueError, HighriseError) as error:
            return response_cls._from_raw(False, str(error))
