from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

Reaction = Literal["clap", "heart", "thumbs", "wave", "wink"]
Facing = Literal["FrontRight", "FrontLeft", "BackRight", "BackLeft"]


@dataclass
class User:
    id: str
    username: str


@dataclass
class Position:
    x: float
    y: float
    z: float
    facing: Facing = "FrontRight"


@dataclass
class AnchorPosition:
    entity_id: str
    anchor_ix: int


@dataclass
class RoomPermissions:
    moderator: bool | None = None
    designer: bool | None = None


@dataclass
class CurrencyItem:
    type: str
    amount: int


class Item:
    """Compatible highrise.models.Item."""

    __slots__ = ("account_bound", "active_palette", "amount", "id", "type")

    def __init__(
        self,
        type: str = "clothing",
        amount: int = 1,
        id: str = "",
        account_bound: bool = False,
        active_palette: int | None = None,
    ) -> None:
        self.type = type
        self.amount = amount
        self.id = id
        self.account_bound = account_bound
        self.active_palette = active_palette

    @property
    def name(self) -> str:
        return self.id

    def __repr__(self) -> str:
        return (
            f"Item(type={self.type!r}, amount={self.amount!r}, id={self.id!r}, "
            f"account_bound={self.account_bound!r}, active_palette={self.active_palette!r})"
        )

    def __eq__(self, other: object) -> bool:
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
        return hash(
            (self.type, self.amount, self.id, self.account_bound, self.active_palette)
        )


class Message:
    """Compatible inbox message object."""

    __slots__ = (
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
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.createdAt = createdAt
        self.content = content
        self.sender_id = sender_id
        self.category = category

    @property
    def id(self) -> str:
        return self.message_id

    @property
    def created_at(self) -> Any:
        return self.createdAt

    @property
    def user_id(self) -> str:
        return self.sender_id

    def __repr__(self) -> str:
        return (
            f"Message(message_id={self.message_id!r}, "
            f"conversation_id={self.conversation_id!r}, "
            f"sender_id={self.sender_id!r}, content={self.content[:40]!r})"
        )


@dataclass
class Conversation:
    id: str
    did_join: bool = False
    unread_count: int = 0
    last_message: Message | None = None
    muted: bool = False
    member_ids: list[str] | None = None
    name: str | None = None
    owner_id: str | None = None


@dataclass
class MessageMedia:
    type: str
    width: int
    height: int
    mediaSizeInBytes: int
    thumbnailSizeInBytes: int
    id: str | None = None
    url: str | None = None
    thumbnailUrl: str | None = None


@dataclass
class RoomInfo:
    owner_id: str
    room_name: str


@dataclass
class SessionMetadata:
    user_id: str
    room_info: RoomInfo
    rate_limits: dict[str, Any] = field(default_factory=dict)
    connection_id: str = ""
    sdk_version: str | None = None


class Error:
    __slots__ = ("do_not_reconnect", "message", "rid")

    def __init__(
        self, message: str = "", do_not_reconnect: bool = False, rid: str | None = None
    ) -> None:
        self.message = message
        self.do_not_reconnect = do_not_reconnect
        self.rid = rid

    def __repr__(self) -> str:
        return (
            f"Error(message={self.message!r}, "
            f"do_not_reconnect={self.do_not_reconnect!r}, rid={self.rid!r})"
        )


# --- Events ---


@dataclass
class ChatEvent:
    user: User
    message: str
    whisper: bool


@dataclass
class EmoteEvent:
    user: User
    emote_id: str
    receiver: User | None = None


@dataclass
class ReactionEvent:
    user: User
    reaction: Reaction
    receiver: User | None = None


@dataclass
class UserJoinedEvent:
    user: User
    position: Position | AnchorPosition | None = None


@dataclass
class UserLeftEvent:
    user: User


@dataclass
class ChannelEvent:
    sender_id: str
    msg: str
    tags: list[str] = field(default_factory=list)


@dataclass
class TipReactionEvent:
    sender: User
    receiver: User
    item: Item | CurrencyItem | None = None


@dataclass
class UserMovedEvent:
    user: User
    position: Position | AnchorPosition | None = None


@dataclass
class VoiceEvent:
    users: list[tuple[User, str]] = field(default_factory=list)
    seconds_left: int = 0


@dataclass
class MessageEvent:
    user_id: str
    conversation_id: str
    is_new_conversation: bool = False


@dataclass
class RoomModeratedEvent:
    moderatorId: str
    targetUserId: str
    moderationType: str
    duration: int | None = None


# --- Responses ---


@dataclass
class GetRoomUsersResponse:
    content: list[tuple[User, Position | AnchorPosition]]
    rid: str | None = None


@dataclass
class GetWalletResponse:
    content: list[CurrencyItem]
    rid: str | None = None


@dataclass
class GetBackpackResponse:
    backpack: Counter[str]
    rid: str | None = None


@dataclass
class ChangeBackpackResponse:
    rid: str | None = None


@dataclass
class GetRoomPrivilegeResponse:
    content: RoomPermissions
    rid: str | None = None


@dataclass
class CheckVoiceChatResponse:
    seconds_left: int
    auto_speakers: set[str]
    users: dict[str, str]
    rid: str | None = None


@dataclass
class GetUserOutfitResponse:
    outfit: list[Item]
    rid: str | None = None


@dataclass
class GetConversationsResponse:
    conversations: list[Conversation]
    not_joined: int
    rid: str | None = None


@dataclass
class SendMessageResponse:
    rid: str | None = None


@dataclass
class SendBulkMessageResponse:
    rid: str | None = None


@dataclass
class GetMessagesResponse:
    messages: list[Message]
    rid: str | None = None


@dataclass
class LeaveConversationResponse:
    rid: str | None = None


@dataclass
class BuyVoiceTimeResponse:
    result: str
    rid: str | None = None


@dataclass
class BuyRoomBoostResponse:
    result: str
    rid: str | None = None


@dataclass
class TipUserResponse:
    result: str
    rid: str | None = None


@dataclass
class GetInventoryResponse:
    items: list[Item]
    rid: str | None = None


@dataclass
class SetOutfitResponse:
    rid: str | None = None


@dataclass
class BuyItemResponse:
    result: str
    rid: str | None = None


@dataclass
class MessageMediaResponse:
    media: MessageMedia | None
    uploadUrl: str | None = None
    thumbnailUploadUrl: str | None = None
    rid: str | None = None


# --- Acks ---


@dataclass
class ChatResponse:
    rid: str | None = None


@dataclass
class EmoteResponse:
    rid: str | None = None


@dataclass
class ReactionResponse:
    rid: str | None = None


@dataclass
class IndicatorResponse:
    rid: str | None = None


@dataclass
class ChannelResponse:
    rid: str | None = None


@dataclass
class KeepaliveResponse:
    rid: str | None = None


@dataclass
class TeleportResponse:
    rid: str | None = None


@dataclass
class FloorHitResponse:
    rid: str | None = None


@dataclass
class AnchorHitResponse:
    rid: str | None = None


@dataclass
class ModerateRoomResponse:
    rid: str | None = None


@dataclass
class ChangeRoomPrivilegeResponse:
    rid: str | None = None


@dataclass
class MoveUserToRoomResponse:
    rid: str | None = None


@dataclass
class InviteSpeakerResponse:
    rid: str | None = None


@dataclass
class RemoveSpeakerResponse:
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
}


# --- Control ---


@dataclass
class ControlSessionMetadata:
    connection_id: str
    instance_ids: list[str]


@dataclass
class InstanceStartedEvent:
    instance_id: str


@dataclass
class InstanceStoppedEvent:
    instance_id: str


class ResponseError(Exception):
    pass


class _DoNotReconnect(Exception):
    pass


# Compatibility with official SDK request class names.
from .compat_requests import *
