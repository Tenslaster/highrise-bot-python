"""Core runtime models for Highrise sessions, events, requests, and responses."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

Reaction = Literal["clap", "heart", "thumbs", "wave", "wink"]
Facing = Literal["FrontRight", "FrontLeft", "BackRight", "BackLeft"]


@dataclass(slots=True, weakref_slot=True)
class User:
    """Highrise user identity."""
    id: str
    username: str


@dataclass(slots=True, weakref_slot=True)
class Position:
    """Absolute floor position with facing direction."""
    x: float
    y: float
    z: float
    facing: Facing = "FrontRight"


@dataclass(slots=True, weakref_slot=True)
class AnchorPosition:
    """Anchor-based position attached to an entity."""
    entity_id: str
    anchor_ix: int


@dataclass(slots=True, weakref_slot=True)
class RoomPermissions:
    """Room privilege flags for a user."""
    moderator: bool | None = None
    designer: bool | None = None


@dataclass(slots=True, weakref_slot=True)
class CurrencyItem:
    """Currency amount and type."""
    type: str
    amount: int


class Item:
    """Compatible highrise.models.Item."""

    __slots__ = (
        "__weakref__",
        "account_bound",
        "active_palette",
        "amount",
        "id",
        "type",
    )

    def __init__(
        self,
        type: str = "clothing",
        amount: int = 1,
        id: str = "",
        account_bound: bool = False,
        active_palette: int | None = None,
    ) -> None:
        """Initialize the instance."""
        self.type = type
        self.amount = amount
        self.id = id
        self.account_bound = account_bound
        self.active_palette = active_palette

    @property
    def name(self) -> str:
        """Return Name."""
        return self.id

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"Item(type={self.type!r}, amount={self.amount!r}, id={self.id!r}, account_bound={self.account_bound!r}, active_palette={self.active_palette!r})"

    def __eq__(self, other: object) -> bool:
        """Return True when this object is equal to the other object."""
        if not isinstance(other, Item):
            return NotImplemented
        return (
            self.type == other.type
            and self.amount == other.amount
            and self.id == other.id
            and self.account_bound == other.account_bound
            and self.active_palette == other.active_palette
        )

    def __hash__(self) -> int:
        """Return a hash value for this object."""
        return hash(
            (self.type, self.amount, self.id, self.account_bound, self.active_palette)
        )


class Message:
    """Compatible inbox message object."""

    __slots__ = (
        "__weakref__",
        "category",
        "content",
        "conversation_id",
        "createdAt",
        "message_id",
        "sender_id",
    )

    def __init__(
        self,
        message_id: str = "",
        conversation_id: str = "",
        createdAt: Any = None,
        content: str = "",
        sender_id: str = "",
        category: str = "text",
    ) -> None:
        """Initialize the instance."""
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.createdAt = createdAt
        self.content = content
        self.sender_id = sender_id
        self.category = category

    @property
    def id(self) -> str:
        """Return Id."""
        return self.message_id

    @property
    def created_at(self) -> Any:
        """Return Created at."""
        return self.createdAt

    @property
    def user_id(self) -> str:
        """Return User id."""
        return self.sender_id

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"Message(message_id={self.message_id!r}, conversation_id={self.conversation_id!r}, sender_id={self.sender_id!r}, content={self.content[:40]!r})"


@dataclass(slots=True, weakref_slot=True)
class Conversation:
    """Conversation metadata and last message state."""
    id: str
    did_join: bool = False
    unread_count: int = 0
    last_message: Message | None = None
    muted: bool = False
    member_ids: list[str] | None = None
    name: str | None = None
    owner_id: str | None = None


@dataclass(slots=True, weakref_slot=True)
class MessageMedia:
    """Media attachment metadata for messages."""
    type: str
    width: int
    height: int
    mediaSizeInBytes: int
    thumbnailSizeInBytes: int
    id: str | None = None
    url: str | None = None
    thumbnailUrl: str | None = None


@dataclass(slots=True, weakref_slot=True)
class RoomInfo:
    """Basic room identity information."""
    owner_id: str
    room_name: str


@dataclass(slots=True, weakref_slot=True)
class SessionMetadata:
    """Metadata received when a bot session starts."""
    user_id: str
    room_info: RoomInfo
    rate_limits: dict[str, Any] = field(default_factory=dict)
    connection_id: str = ""
    sdk_version: str | None = None


class Error:
    """Server error payload."""
    __slots__ = ("do_not_reconnect", "message", "rid")

    def __init__(
        self, message: str = "", do_not_reconnect: bool = False, rid: str | None = None
    ) -> None:
        """Initialize the instance."""
        self.message = message
        self.do_not_reconnect = do_not_reconnect
        self.rid = rid

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""
        return f"Error(message={self.message!r}, do_not_reconnect={self.do_not_reconnect!r}, rid={self.rid!r})"


@dataclass(slots=True, weakref_slot=True)
class ChatEvent:
    """Chat or whisper event."""
    user: User
    message: str
    whisper: bool


@dataclass(slots=True, weakref_slot=True)
class EmoteEvent:
    """Emote event."""
    user: User
    emote_id: str
    receiver: User | None = None


@dataclass(slots=True, weakref_slot=True)
class ReactionEvent:
    """Reaction event."""
    user: User
    reaction: Reaction
    receiver: User | None = None


@dataclass(slots=True, weakref_slot=True)
class UserJoinedEvent:
    """User joined room event."""
    user: User
    position: Position | AnchorPosition | None = None


@dataclass(slots=True, weakref_slot=True)
class UserLeftEvent:
    """User left room event."""
    user: User


@dataclass(slots=True, weakref_slot=True)
class ChannelEvent:
    """Channel message event."""
    sender_id: str
    msg: str
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True, weakref_slot=True)
class TipReactionEvent:
    """Tip reaction event."""
    sender: User
    receiver: User
    item: Item | CurrencyItem | None = None


@dataclass(slots=True, weakref_slot=True)
class UserMovedEvent:
    """User moved event."""
    user: User
    position: Position | AnchorPosition | None = None


@dataclass(slots=True, weakref_slot=True)
class VoiceEvent:
    """Voice chat state event."""
    users: list[tuple[User, str]] = field(default_factory=list)
    seconds_left: int = 0


@dataclass(slots=True, weakref_slot=True)
class MessageEvent:
    """Inbox message event."""
    user_id: str
    conversation_id: str
    is_new_conversation: bool = False


@dataclass(slots=True, weakref_slot=True)
class RoomModeratedEvent:
    """Room moderation event."""
    moderatorId: str
    targetUserId: str
    moderationType: str
    duration: int | None = None


@dataclass(slots=True, weakref_slot=True)
class GetRoomUsersResponse:
    """Response payload for GetRoomUsersResponse."""
    content: list[tuple[User, Position | AnchorPosition]]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetWalletResponse:
    """Response payload for GetWalletResponse."""
    content: list[CurrencyItem]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetBackpackResponse:
    """Response payload for GetBackpackResponse."""
    backpack: Counter[str]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class ChangeBackpackResponse:
    """Response payload for ChangeBackpackResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetRoomPrivilegeResponse:
    """Response payload for GetRoomPrivilegeResponse."""
    content: RoomPermissions
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class CheckVoiceChatResponse:
    """Response payload for CheckVoiceChatResponse."""
    seconds_left: int
    auto_speakers: set[str]
    users: dict[str, str]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetUserOutfitResponse:
    """Response payload for GetUserOutfitResponse."""
    outfit: list[Item]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetConversationsResponse:
    """Response payload for GetConversationsResponse."""
    conversations: list[Conversation]
    not_joined: int
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class SendMessageResponse:
    """Response payload for SendMessageResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class SendBulkMessageResponse:
    """Response payload for SendBulkMessageResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetMessagesResponse:
    """Response payload for GetMessagesResponse."""
    messages: list[Message]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class LeaveConversationResponse:
    """Response payload for LeaveConversationResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class BuyVoiceTimeResponse:
    """Response payload for BuyVoiceTimeResponse."""
    result: str
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class BuyRoomBoostResponse:
    """Response payload for BuyRoomBoostResponse."""
    result: str
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class TipUserResponse:
    """Response payload for TipUserResponse."""
    result: str
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class GetInventoryResponse:
    """Response payload for GetInventoryResponse."""
    items: list[Item]
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class SetOutfitResponse:
    """Response payload for SetOutfitResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class BuyItemResponse:
    """Response payload for BuyItemResponse."""
    result: str
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class MessageMediaResponse:
    """Response payload for MessageMediaResponse."""
    media: MessageMedia | None
    uploadUrl: str | None = None
    thumbnailUploadUrl: str | None = None
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class ChatResponse:
    """Response payload for ChatResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class EmoteResponse:
    """Response payload for EmoteResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class ReactionResponse:
    """Response payload for ReactionResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class IndicatorResponse:
    """Response payload for IndicatorResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class ChannelResponse:
    """Response payload for ChannelResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class KeepaliveResponse:
    """Response payload for KeepaliveResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class TeleportResponse:
    """Response payload for TeleportResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class FloorHitResponse:
    """Response payload for FloorHitResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class AnchorHitResponse:
    """Response payload for AnchorHitResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class ModerateRoomResponse:
    """Response payload for ModerateRoomResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class ChangeRoomPrivilegeResponse:
    """Response payload for ChangeRoomPrivilegeResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class MoveUserToRoomResponse:
    """Response payload for MoveUserToRoomResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class InviteSpeakerResponse:
    """Response payload for InviteSpeakerResponse."""
    rid: str | None = None


@dataclass(slots=True, weakref_slot=True)
class RemoveSpeakerResponse:
    """Response payload for RemoveSpeakerResponse."""
    rid: str | None = None


_ACK_MAP: dict[str, type] = {
    "ChatResponse": ChatResponse,
    "EmoteResponse": EmoteResponse,
    "ReactionResponse": ReactionResponse,
    "IndicatorResponse": IndicatorResponse,
    "ChannelResponse": ChannelResponse,
    "KeepaliveResponse": KeepaliveResponse,
    "TeleportResponse": TeleportResponse,
    "FloorHitResponse": FloorHitResponse,
    "AnchorHitResponse": AnchorHitResponse,
    "ModerateRoomResponse": ModerateRoomResponse,
    "ChangeRoomPrivilegeResponse": ChangeRoomPrivilegeResponse,
    "MoveUserToRoomResponse": MoveUserToRoomResponse,
    "InviteSpeakerResponse": InviteSpeakerResponse,
    "RemoveSpeakerResponse": RemoveSpeakerResponse,
    "SendMessageResponse": SendMessageResponse,
    "SendBulkMessageResponse": SendBulkMessageResponse,
    "LeaveConversationResponse": LeaveConversationResponse,
    "ChangeBackpackResponse": ChangeBackpackResponse,
    "SetOutfitResponse": SetOutfitResponse,
}


@dataclass(slots=True, weakref_slot=True)
class ControlSessionMetadata:
    """Metadata received when a control session starts."""
    connection_id: str
    instance_ids: list[str]


@dataclass(slots=True, weakref_slot=True)
class InstanceStartedEvent:
    """Control event emitted when a bot instance starts."""
    instance_id: str


@dataclass(slots=True, weakref_slot=True)
class InstanceStoppedEvent:
    """Control event emitted when a bot instance stops."""
    instance_id: str


class ResponseError(Exception):
    """Raised when an API or RPC response reports an error."""
    pass


class _DoNotReconnect(Exception):
    """Internal exception used to stop reconnecting."""
    pass


from .compat_requests import *  # noqa: E402,F401,F403
