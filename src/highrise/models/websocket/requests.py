from dataclasses import dataclass, field
from typing import Any
from .highrise_models import (
    ModerationType,
    TipType,
    RoomPermissions,
    OutfitItem,
    AnchorPosition,
    Position
)

def _base_payload(type_name: str) -> dict[str, Any]:
    return { "_type": type_name } 

@dataclass(frozen=True)
class ChatRequest:
    message: str
    whisper_target_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("ChatRequest")
        payload["message"] = self.message
        if self.whisper_target_id is not None:
            payload["whisper_target_id"] = self.whisper_target_id
        return payload

@dataclass(frozen=True)
class ChannelRequest:
    message: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("ChannelRequest")
        payload.update({
            "message": self.message,
            "tags": self.tags,
        })
        return payload

@dataclass(frozen=True)
class SendMessageRequest:
    conversation_id: str = ""
    user_ids: list[str] = field(default_factory=list)
    type: str = "text"
    content: str = ""
    room_id: str = ""
    world_id: str = ""
    is_bulk: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("SendBulkMessageRequest" if self.is_bulk else "SendMessageRequest")
        payload.update({
            "type": self.type,
            "content": self.content,
            "room_id": self.room_id,
            "world_id": self.world_id,
        })

        if self.is_bulk:
            payload["user_ids"] = self.user_ids
        else:
            payload["conversation_id"] = self.conversation_id

        return payload

@dataclass(frozen=True)
class LeaveConversationRequest:
    conversation_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("LeaveConversationRequest")
        payload.update({
            "conversation_id": self.conversation_id,
        })
        return payload

@dataclass(frozen=True)
class GetMessagesRequest:
    conversation_id: str
    last_message_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("GetMessagesRequest")
        payload.update({
            "conversation_id": self.conversation_id,
            "last_message_id": self.last_message_id,
        })
        return payload

@dataclass(frozen=True)
class GetConversationsRequest:
    not_joined: bool = False
    last_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("GetConversationsRequest")
        payload.update({
            "not_joined": self.not_joined,
            "last_id": self.last_id,
        })
        return payload
    
@dataclass(frozen=True)
class EmoteRequest:
    emote_id: str
    target_user_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("EmoteRequest")
        payload["emote_id"] = self.emote_id
        payload["target_user_id"] = self.target_user_id
        return payload

@dataclass(frozen=True)
class AnchorHitRequest:
    """Move the bot to the given anchor position."""
    anchor: AnchorPosition

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("AnchorHitRequest")
        payload.update({
            "anchor": {
                "entity_id": self.anchor.entity_id,
                "anchor_ix": self.anchor.anchor_ix,
            },
        })
        return payload

@dataclass(frozen=True)
class TeleportRequest:
    """Move a user to the given floor position."""
    user_id: str
    destination: Position

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("TeleportRequest")
        payload.update({
            "user_id": self.user_id,
            "destination": {
                "x": self.destination.x,
                "y": self.destination.y,
                "z": self.destination.z,
                "facing": self.destination.facing,
            },
        })
        return payload

@dataclass(frozen=True)
class FloorHitRequest:
    """Move the bot to the given floor destination."""
    destination: Position

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("FloorHitRequest")
        payload.update({
            "destination": {
                "x": self.destination.x,
                "y": self.destination.y,
                "z": self.destination.z,
                "facing": self.destination.facing,
            },
        })
        return payload

@dataclass(frozen=True)
class ModerateRoomRequest:
    """Moderate a user in the room: kick, ban, unban, or mute."""
    user_id: str
    moderation_action: ModerationType
    action_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("ModerateRoomRequest")
        payload.update({
            "user_id": self.user_id,
            "moderation_action": self.moderation_action,
            "action_length": self.action_length,
        })
        return payload

@dataclass(frozen=True)
class TipUserRequest:
    """Tip a user with a gold bar amount."""
    user_id: str
    gold_bar: TipType

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("TipUserRequest")
        payload.update({
            "user_id": self.user_id,
            "gold_bar": self.gold_bar,
        })
        return payload

@dataclass(frozen=True)
class GetUserOutfitRequest:
    """Fetch the outfit for a user."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("GetUserOutfitRequest")
        payload.update({
            "user_id": self.user_id,
        })
        return payload

@dataclass(frozen=True)
class MoveUserToRoomRequest:
    """Move a user to a different room. Only works if the bot belongs
    to the owner of the target room, or has designer privileges."""
    user_id: str
    room_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("MoveUserToRoomRequest")
        payload.update({
            "user_id": self.user_id,
            "room_id": self.room_id,
        })
        return payload

@dataclass(frozen=True)
class GetRoomUsersRequest:
    """Fetch the list of users currently in the room, with their positions."""

    def to_dict(self) -> dict[str, Any]:
        return _base_payload("GetRoomUsersRequest")

@dataclass(frozen=True)
class CheckVoiceChatRequest:
    """Fetch the voice status for the room."""

    def to_dict(self) -> dict[str, Any]:
        return _base_payload("CheckVoiceChatRequest")


@dataclass(frozen=True)
class InviteSpeakerRequest:
    """Add a user to voice chat."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("InviteSpeakerRequest")
        payload.update({
            "user_id": self.user_id,
        })
        return payload


@dataclass(frozen=True)
class RemoveSpeakerRequest:
    """Remove a user from voice chat."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("RemoveSpeakerRequest")
        payload.update({
            "user_id": self.user_id,
        })
        return payload

@dataclass(frozen=True)
class GetRoomPrivilegeRequest:
    """Fetch the room privilege for a given user."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("GetRoomPrivilegeRequest")
        payload.update({
            "user_id": self.user_id,
        })
        return payload

@dataclass(frozen=True)
class ChangeRoomPrivilegeRequest:
    """Change the room privilege for a given user."""
    user_id: str
    permissions: RoomPermissions

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("ChangeRoomPrivilegeRequest")
        payload.update({
            "user_id": self.user_id,
            "permissions": {
                "moderator": self.permissions.moderator,
                "designer": self.permissions.designer,
            },
        })
        return payload

@dataclass(frozen=True)
class GetWalletRequest:
    """Fetch the bot's wallet."""

    def to_dict(self) -> dict[str, Any]:
        return _base_payload("GetWalletRequest")

@dataclass(frozen=True)
class BuyItemRequest:
    """Buy an item."""
    item_id: str

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("BuyItemRequest")
        payload.update({
            "item_id": self.item_id,
        })
        return payload

@dataclass(frozen=True)
class GetInventoryRequest:
    """Get the bot's inventory."""

    def to_dict(self) -> dict[str, Any]:
        return _base_payload("GetInventoryRequest")

@dataclass(frozen=True)
class SetOutfitRequest:
    """Set the outfit of a bot."""
    outfit: list[OutfitItem]

    def to_dict(self) -> dict[str, Any]:
        payload = _base_payload("SetOutfitRequest")
        payload.update({
            "outfit": [
                {
                    "type": item.type,
                    "amount": item.amount,
                    "id": item.id,
                    "account_bound": item.account_bound,
                    "active_palette": item.active_palette,
                }
                for item in self.outfit
            ],
        })
        return payload