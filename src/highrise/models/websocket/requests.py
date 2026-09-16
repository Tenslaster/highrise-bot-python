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

@dataclass(frozen=True, slots=True)
class ChatRequest:
    message: str
    whisper_target_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"_type": "ChatRequest", "message": self.message}
        if self.whisper_target_id is not None:
            payload["whisper_target_id"] = self.whisper_target_id
        return payload

@dataclass(frozen=True, slots=True)
class ChannelRequest:
    message: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "ChannelRequest",
            "message": self.message,
            "tags": self.tags,
        }

@dataclass(frozen=True, slots=True)
class SendMessageRequest:
    conversation_id: str = ""
    user_ids: list[str] = field(default_factory=list)
    type: str = "text"
    content: str = ""
    room_id: str = ""
    world_id: str = ""
    is_bulk: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "_type": "SendBulkMessageRequest" if self.is_bulk else "SendMessageRequest",
            "type": self.type,
            "content": self.content,
            "room_id": self.room_id,
            "world_id": self.world_id,
        }
        if self.is_bulk:
            payload["user_ids"] = self.user_ids
        else:
            payload["conversation_id"] = self.conversation_id
        return payload

@dataclass(frozen=True, slots=True)
class LeaveConversationRequest:
    conversation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "LeaveConversationRequest",
            "conversation_id": self.conversation_id,
        }

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
        return {
            "_type": "GetConversationsRequest",
            "not_joined": self.not_joined,
            "last_id": self.last_id,
        }
    
@dataclass(frozen=True, slots=True)
class EmoteRequest:
    emote_id: str
    target_user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "EmoteRequest",
            "emote_id": self.emote_id,
            "target_user_id": self.target_user_id,
        }

@dataclass(frozen=True, slots=True)
class AnchorHitRequest:
    """Move the bot to the given anchor position."""
    anchor: AnchorPosition

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "AnchorHitRequest",
            "anchor": {
                "entity_id": self.anchor.entity_id,
                "anchor_ix": self.anchor.anchor_ix,
            },
        }

@dataclass(frozen=True, slots=True)
class TeleportRequest:
    """Move a user to the given floor position."""
    user_id: str
    destination: Position

    def to_dict(self) -> dict[str, Any]:
        dest = self.destination
        return {
            "_type": "TeleportRequest",
            "user_id": self.user_id,
            "destination": {
                "x": dest.x,
                "y": dest.y,
                "z": dest.z,
                "facing": dest.facing,
            },
        }

@dataclass(frozen=True, slots=True)
class FloorHitRequest:
    """Move the bot to the given floor destination."""
    destination: Position

    def to_dict(self) -> dict[str, Any]:
        dest = self.destination
        return {
            "_type": "FloorHitRequest",
            "destination": {
                "x": dest.x,
                "y": dest.y,
                "z": dest.z,
                "facing": dest.facing,
            },
        }

@dataclass(frozen=True, slots=True)
class ModerateRoomRequest:
    """Moderate a user in the room: kick, ban, unban, or mute."""
    user_id: str
    moderation_action: ModerationType
    action_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "ModerateRoomRequest",
            "user_id": self.user_id,
            "moderation_action": self.moderation_action,
            "action_length": self.action_length,
        }

@dataclass(frozen=True, slots=True)
class TipUserRequest:
    """Tip a user with a gold bar amount."""
    user_id: str
    gold_bar: TipType

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "TipUserRequest",
            "user_id": self.user_id,
            "gold_bar": self.gold_bar,
        }

@dataclass(frozen=True, slots=True)
class GetUserOutfitRequest:
    """Fetch the outfit for a user."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "GetUserOutfitRequest",
            "user_id": self.user_id,
        }

@dataclass(frozen=True, slots=True)
class MoveUserToRoomRequest:
    """Move a user to a different room. Only works if the bot belongs
    to the owner of the target room, or has designer privileges."""
    user_id: str
    room_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "MoveUserToRoomRequest",
            "user_id": self.user_id,
            "room_id": self.room_id,
        }

@dataclass(frozen=True, slots=True)
class GetRoomUsersRequest:
    """Fetch the list of users currently in the room, with their positions."""

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetRoomUsersRequest"}

@dataclass(frozen=True, slots=True)
class CheckVoiceChatRequest:
    """Fetch the voice status for the room."""

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "CheckVoiceChatRequest"}

@dataclass(frozen=True, slots=True)
class InviteSpeakerRequest:
    """Add a user to voice chat."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "InviteSpeakerRequest",
            "user_id": self.user_id,
        }

@dataclass(frozen=True, slots=True)
class RemoveSpeakerRequest:
    """Remove a user from voice chat."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "RemoveSpeakerRequest",
            "user_id": self.user_id,
        }

@dataclass(frozen=True, slots=True)
class GetRoomPrivilegeRequest:
    """Fetch the room privilege for a given user."""
    user_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "GetRoomPrivilegeRequest",
            "user_id": self.user_id,
        }

@dataclass(frozen=True, slots=True)
class ChangeRoomPrivilegeRequest:
    """Change the room privilege for a given user."""
    user_id: str
    permissions: RoomPermissions

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "ChangeRoomPrivilegeRequest",
            "user_id": self.user_id,
            "permissions": {
                "moderator": self.permissions.moderator,
                "designer": self.permissions.designer,
            },
        }

@dataclass(frozen=True, slots=True)
class GetWalletRequest:
    """Fetch the bot's wallet."""

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetWalletRequest"}

@dataclass(frozen=True, slots=True)
class BuyItemRequest:
    """Buy an item."""
    item_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "BuyItemRequest",
            "item_id": self.item_id,
        }

@dataclass(frozen=True, slots=True)
class GetInventoryRequest:
    """Get the bot's inventory."""

    def to_dict(self) -> dict[str, Any]:
        return {"_type": "GetInventoryRequest"}

@dataclass(frozen=True, slots=True)
class SetOutfitRequest:
    """Set the outfit of a bot."""
    outfit: list[OutfitItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "_type": "SetOutfitRequest",
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
        }