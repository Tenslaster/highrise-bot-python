from __future__ import annotations

from typing import Any, TYPE_CHECKING
from collections.abc import Callable

from .errors import HighriseError
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

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any:
        payload = build_payload()
        try:
            success, data = await self._context.requester.send(
                payload,
                timeout=self._context.requester.default_timeout,
            )
            return response_cls._from_raw(success, data)
        except ValueError as error:
            return response_cls._from_raw(success=False, data=str(error))
        except HighriseError as error:
            return response_cls._from_raw(success=False, data=str(error))
