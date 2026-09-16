from dataclasses import dataclass, field
from typing import Any

from .highrise_models import (
    ModerationType,
    TipType,
    RoomPermissions,
    OutfitItem,
    AnchorPosition,
    Position,
)


def _base_payload(type_name: str) -> dict[str, Any]:
    return {"_type": type_name}


@dataclass(frozen=True, slots=True)
class ChatRequest:
    message: str
    whisper_target_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"_type": "ChatRequest", "message": self.message}
        if self.whisper_target_id is not None:
            payload["whisper_target_id"] = self.whisper_target_id
        return payload


@dataclass(frozen=True, slots=True)
class ChannelRequest:
    message: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "ChannelRequest", "message": self.message, "tags": self.tags}


@dataclass(frozen=True, slots=True)
class SendMessageRequest:
    conversation_id: str = ""
    user_ids: list[str] = field(default_factory=list)
    type: str = "text"
    content: str = ""
    room_id: str | None = None
    world_id: str | None = None
    is_bulk: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "_type": "SendBulkMessageRequest" if self.is_bulk else "SendMessageRequest",
            "type": self.type,
            "content": self.content,
        }
        if self.room_id is not None:
            payload["room_id"] = self.room_id
        if self.world_id is not None:
            payload["world_id"] = self.world_id
        if self.is_bulk:
            payload["user_ids"] = self.user_ids
        else:
            payload["conversation_id"] = self.conversation_id
        return payload


@dataclass(frozen=True, slots=True)
class LeaveConversationRequest:
    conversation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "LeaveConversationRequest", "conversation_id": self.conversation_id}


@dataclass(frozen=True, slots=True)
class GetMessagesRequest:
    conversation_id: str
    last_message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "GetMessagesRequest",
            "conversation_id": self.conversation_id,
            "last_message_id": self.last_message_id,
        }


@dataclass(frozen=True, slots=True)
class GetConversationsRequest:
    not_joined: bool = False
    last_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetConversationsRequest", "not_joined": self.not_joined, "last_id": self.last_id}


@dataclass(frozen=True, slots=True)
class EmoteRequest:
    """Wire-compatible Highrise emote request.

    ``target_user_id`` is optional: omitting it performs the emote on the bot,
    matching the original SDK's ``EmoteRequest(emote_id, target_user_id)``.
    """

    emote_id: str
    target_user_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {"_type": "EmoteRequest", "emote_id": self.emote_id}
        if self.target_user_id is not None:
            payload["target_user_id"] = self.target_user_id
        return payload


@dataclass(frozen=True, slots=True)
class AnchorHitRequest:
    anchor: AnchorPosition

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "AnchorHitRequest", "anchor": {"entity_id": self.anchor.entity_id, "anchor_ix": self.anchor.anchor_ix}}


@dataclass(frozen=True, slots=True)
class TeleportRequest:
    user_id: str
    destination: Position

    def to_dict(self) -> dict[str, Any]:
        d = self.destination
        return {"_type": "TeleportRequest", "user_id": self.user_id, "destination": {"x": d.x, "y": d.y, "z": d.z, "facing": d.facing}}


@dataclass(frozen=True, slots=True)
class FloorHitRequest:
    destination: Position

    def to_dict(self) -> dict[str, Any]:
        d = self.destination
        return {"_type": "FloorHitRequest", "destination": {"x": d.x, "y": d.y, "z": d.z, "facing": d.facing}}


@dataclass(frozen=True, slots=True)
class ModerateRoomRequest:
    user_id: str
    moderation_action: ModerationType
    action_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "ModerateRoomRequest", "user_id": self.user_id, "moderation_action": self.moderation_action, "action_length": self.action_length}


@dataclass(frozen=True, slots=True)
class TipUserRequest:
    user_id: str
    gold_bar: TipType

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "TipUserRequest", "user_id": self.user_id, "gold_bar": self.gold_bar}


@dataclass(frozen=True, slots=True)
class GetUserOutfitRequest:
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetUserOutfitRequest", "user_id": self.user_id}


@dataclass(frozen=True, slots=True)
class MoveUserToRoomRequest:
    user_id: str
    room_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "MoveUserToRoomRequest", "user_id": self.user_id, "room_id": self.room_id}


@dataclass(frozen=True, slots=True)
class GetRoomUsersRequest:
    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetRoomUsersRequest"}


@dataclass(frozen=True, slots=True)
class CheckVoiceChatRequest:
    def to_dict(self) -> dict[str, Any]:
        return {"_type": "CheckVoiceChatRequest"}


@dataclass(frozen=True, slots=True)
class InviteSpeakerRequest:
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "InviteSpeakerRequest", "user_id": self.user_id}


@dataclass(frozen=True, slots=True)
class RemoveSpeakerRequest:
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "RemoveSpeakerRequest", "user_id": self.user_id}


@dataclass(frozen=True, slots=True)
class GetRoomPrivilegeRequest:
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetRoomPrivilegeRequest", "user_id": self.user_id}


@dataclass(frozen=True, slots=True)
class ChangeRoomPrivilegeRequest:
    user_id: str
    permissions: RoomPermissions

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "ChangeRoomPrivilegeRequest", "user_id": self.user_id, "permissions": {"moderator": self.permissions.moderator, "designer": self.permissions.designer}}


@dataclass(frozen=True, slots=True)
class GetWalletRequest:
    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetWalletRequest"}


@dataclass(frozen=True, slots=True)
class BuyItemRequest:
    item_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "BuyItemRequest", "item_id": self.item_id}


@dataclass(frozen=True, slots=True)
class GetInventoryRequest:
    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetInventoryRequest"}


@dataclass(frozen=True, slots=True)
class SetOutfitRequest:
    outfit: list[OutfitItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "SetOutfitRequest",
            "outfit": [
                {"type": item.type, "amount": item.amount, "id": item.id, "account_bound": item.account_bound, "active_palette": item.active_palette}
                for item in self.outfit
            ],
        }


__all__ = [name for name in globals() if name.endswith("Request")]
