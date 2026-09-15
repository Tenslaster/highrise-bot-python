from typing import Any
from collections.abc import Callable
import asyncio

from ...models.websocket.responses import AcknowledgementResponse, TipUserResponse, GetUserOutfitResponse
from ...models.websocket.requests import (
    EmoteRequest, 
    AnchorHitRequest, 
    TeleportRequest,
    ModerateRoomRequest,
    FloorHitRequest,
    TipUserRequest,
    GetUserOutfitRequest,
    MoveUserToRoomRequest
)

from ...tools.utils import Utils
from ...tools.validator import Validator

from ...models.websocket.highrise_models import *

TIP_SPLIT_DELAY = 0.4

class PlayerMixin:
    """Player-related methods: `emote`, `moderation`, `teleport`, other actions."""
    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def send_emote(self, emote_id: str, target_user_id: str | None = None) -> AcknowledgementResponse:
        """Perform an emote directed toward a specific player, if no `target_user_id` provided it will be performed on the bot."""

        def build() -> dict:
            Validator.required(emote_id, "emote_id")
            Validator.string(emote_id, "emote_id")
            Validator.string(target_user_id, "target_user_id")

            request = EmoteRequest(emote_id=emote_id, target_user_id=target_user_id)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)

    async def walk_to(self, destination: Position | AnchorPosition) -> AcknowledgementResponse:
        """Moves the bot to the given floor position or anchor position."""

        def build() -> dict:
            Validator.required(destination, "destination")

            if isinstance(destination, AnchorPosition):
                request = AnchorHitRequest(anchor=destination)
            else:
                request = FloorHitRequest(destination=destination)

            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)

    async def teleport(self, user_id: str, destination: Position) -> AcknowledgementResponse:
        """Teleports a user to the given floor position."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")
            Validator.required(destination, "destination")

            request = TeleportRequest(user_id=user_id, destination=destination)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)

    async def moderate_room(
        self,
        user_id: str,
        action: ModerationType,
        action_length: int | None = None,
    ) -> AcknowledgementResponse:
        """Moderate a user in the room: kick, ban, unban, or mute."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")
            Validator.required(action, "action")
            Validator.one_of(action, ("kick", "ban", "unban", "mute"), "action")

            if action_length is not None:
                year_in_sec = 60 * 365 * 24 * 3600
                min_in_sec = 60

                Validator.range(action_length, min_in_sec, year_in_sec, "action_length")

            request = ModerateRoomRequest(
                user_id=user_id,
                moderation_action=action,
                action_length=action_length,
            )
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)

    async def kick(self, user_id: str) -> AcknowledgementResponse:
        """Kicks a user from the room."""
        return await self.moderate_room(user_id, "kick")

    async def ban(self, user_id: str, action_length: int = 86400) -> AcknowledgementResponse:
        """Bans a user from the room. Defaults to 1 day."""
        return await self.moderate_room(user_id, "ban", action_length)

    async def unban(self, user_id: str) -> AcknowledgementResponse:
        """Unbans a user from the room."""
        return await self.moderate_room(user_id, "unban")

    async def mute(self, user_id: str, action_length: int = 3600) -> AcknowledgementResponse:
        """Mutes a user in the room. Defaults to 1 hour."""
        return await self.moderate_room(user_id, "mute", action_length)

    async def unmute(self, user_id: str) -> AcknowledgementResponse:
        """Unmutes a user in the room."""
        return await self.moderate_room(user_id, "mute", 1)

    async def tip_user(self, user_id: str, tip: TipType) -> "TipUserResponse":
        """Tips a user with the given gold bar amount."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")
            Validator.required(tip, "tip")
            Validator.one_of(tip, TIP_VALUES.values(), "tip")

            request = TipUserRequest(user_id=user_id, gold_bar=tip)
            return request.to_dict()

        return await self._send_request(TipUserResponse, build)

    async def split_tip_user(self, user_id: str, amount: int) -> list[TipUserResponse]:
        """Tips a user the given gold amount, automatically decomposed into
        valid tip tiers and sent sequentially with a short delay of `400ms` between
        each. Stops and returns early if any tip fails."""
        tiers = Utils.split_tip(amount)
        responses: list[TipUserResponse] = []

        for i, tier in enumerate(tiers):
            response = await self.tip_user(user_id, tier)
            responses.append(response)

            if not response.ok or response.result != "success":
                break

            if i < len(tiers) - 1:
                await asyncio.sleep(TIP_SPLIT_DELAY)

        return responses

    async def get_user_outfit(self, user_id: str) -> GetUserOutfitResponse:
        """Fetches the outfit for a user."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")

            request = GetUserOutfitRequest(user_id=user_id)
            return request.to_dict()

        return await self._send_request(GetUserOutfitResponse, build)

    async def move_user_to_room(self, user_id: str, room_id: str) -> AcknowledgementResponse:
        """Attempt to move a user to a different room.

        This will only work if the bot belongs to the owner of the
        target room, or has designer privileges.
        """

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")
            Validator.required(room_id, "room_id")
            Validator.string(room_id, "room_id")

            request = MoveUserToRoomRequest(user_id=user_id, room_id=room_id)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)