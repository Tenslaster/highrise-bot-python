from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal

from .models.base_response import BaseResponse
from .models.websocket.responses import AcknowledgementResponse
from .models.websocket.highrise_models import Item, OutfitItem, RoomPermissions


@dataclass(slots=True)
class ContentResponse(BaseResponse):
    content: Any = None

    def _build(self, data: Any) -> None:
        self.content = data.get("content") if isinstance(data, dict) else data


@dataclass(slots=True)
class ResultResponse(BaseResponse):
    result: str | None = None

    def _build(self, data: Any) -> None:
        if isinstance(data, dict):
            self.result = data.get("result")


class CompatibilityMixin:
    """Compatibility facade for methods present in the original Highrise SDK."""

    async def _send_request(self, response_cls: Any, build_payload): ...

    async def react(self, reaction: str, target_user_id: str) -> AcknowledgementResponse:
        if reaction not in {"clap", "heart", "thumbs", "wave", "wink"}:
            raise ValueError("reaction must be clap, heart, thumbs, wave, or wink")
        if not isinstance(target_user_id, str) or not target_user_id:
            raise ValueError("target_user_id must be a non-empty string")
        return await self._send_request(AcknowledgementResponse, lambda: {
            "_type": "ReactionRequest",
            "reaction": reaction,
            "target_user_id": target_user_id,
        })

    async def set_indicator(self, icon: str | None) -> AcknowledgementResponse:
        if icon is not None and not isinstance(icon, str):
            raise TypeError("icon must be str | None")
        return await self._send_request(AcknowledgementResponse, lambda: {
            "_type": "IndicatorRequest", "icon": icon,
        })

    async def get_backpack(self, user_id: str) -> ContentResponse:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")
        return await self._send_request(ContentResponse, lambda: {
            "_type": "GetBackpackRequest", "user_id": user_id,
        })

    async def change_backpack(self, user_id: str, changes: dict[str, int]) -> ContentResponse:
        if not isinstance(user_id, str) or not user_id:
            raise ValueError("user_id must be a non-empty string")
        if not isinstance(changes, dict) or any(not isinstance(k, str) or not isinstance(v, int) for k, v in changes.items()):
            raise TypeError("changes must be dict[str, int]")
        return await self._send_request(ContentResponse, lambda: {
            "_type": "ChangeBackpackRequest", "user_id": user_id, "changes": changes,
        })

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        message_type: Literal["text", "invite"] = "text",
        room_id: str | None = None,
        world_id: str | None = None,
    ) -> None | AcknowledgementResponse:
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError("conversation_id must be a non-empty string")
        if not isinstance(content, str):
            raise TypeError("content must be a string")
        payload = {
            "_type": "SendMessageRequest", "conversation_id": conversation_id,
            "content": content, "type": message_type,
            "room_id": room_id, "world_id": world_id,
        }
        response = await self._send_request(AcknowledgementResponse, lambda: payload)
        return None if response.ok else response

    async def send_message_bulk(
        self,
        user_ids: list[str],
        content: str,
        message_type: Literal["text", "invite"] = "text",
        room_id: str | None = None,
        world_id: str | None = None,
    ) -> None | AcknowledgementResponse:
        if not isinstance(user_ids, list) or not all(isinstance(uid, str) and uid for uid in user_ids):
            raise TypeError("user_ids must be list[str]")
        if len(user_ids) > 100:
            raise ValueError("user_ids cannot contain more than 100 users")
        payload = {
            "_type": "SendBulkMessageRequest", "user_ids": user_ids,
            "content": content, "type": message_type,
            "room_id": room_id, "world_id": world_id,
        }
        response = await self._send_request(AcknowledgementResponse, lambda: payload)
        return None if response.ok else response

    async def buy_voice_time(self, payment: str = "bot_wallet_only") -> str | ResultResponse:
        response = await self._send_request(ResultResponse, lambda: {
            "_type": "BuyVoiceTimeRequest", "payment": payment,
        })
        return response.result if response.ok else response

    async def buy_room_boost(self, payment: str = "bot_wallet_only", amount: int = 1) -> str | ResultResponse:
        if amount < 1:
            raise ValueError("amount must be >= 1")
        response = await self._send_request(ResultResponse, lambda: {
            "_type": "BuyRoomBoostRequest", "payment": payment, "amount": amount,
        })
        return response.result if response.ok else response

    def call_in(self, callback, delay: float) -> asyncio.Task:
        if delay < 0:
            raise ValueError("delay must be >= 0")
        return asyncio.create_task(self._delayed_callback(callback, delay))

    @staticmethod
    async def _delayed_callback(callback, delay: float) -> None:
        await asyncio.sleep(delay)
        result = callback()
        if hasattr(result, "__await__"):
            await result
