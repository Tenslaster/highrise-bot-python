#!/usr/bin/env python3
"""
highrise_fast — standalone Highrise SDK replacement.
Features:
- No monkey patching
- No attrs/cattrs dependency
- Optional orjson fast path
- Direct websocket bytes sending
- Request/response cleanup (no leaks)
- sdk_fast compatibility layer
- highrise.models compatibility
- highrise.webapi compatibility
- Typed event classes matching official SDK
- Wire format correctness
- CLI compatible with:
python -m highrise_fast module:BotClass ROOM_ID API_TOKEN
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import os
import sys
import time
import types
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import isawaitable
from itertools import count
from typing import Any, Literal, Self

try:
    import orjson
except ImportError:
    orjson = None

try:
    from aiohttp import ClientSession, WebSocketError, WSMsgType, WSServerHandshakeError
except ImportError as exc:
    raise SystemExit("Missing dependency: pip install aiohttp") from exc

try:
    from quattro import TaskGroup
except ImportError:
    TaskGroup = getattr(asyncio, "TaskGroup", None)
    if TaskGroup is None:

        class TaskGroup:
            def __init__(self) -> None:
                self._tasks: list[asyncio.Task] = []

            async def __aenter__(self) -> Self:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> bool:
                if self._tasks:
                    await asyncio.gather(*self._tasks, return_exceptions=True)
                return False

            def create_task(self, coro):
                task = asyncio.create_task(coro)
                self._tasks.append(task)
                return task


# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------
__version__ = "1.0.0"
__all__ = [
    "AnchorHitResponse",
    "AnchorPosition",
    "BaseBot",
    "BotDefinition",
    "BuyItemResponse",
    "BuyRoomBoostResponse",
    "BuyVoiceTimeResponse",
    "ChangeBackpackResponse",
    "ChangeRoomPrivilegeResponse",
    "ChannelEvent",
    "ChannelResponse",
    "ChatEvent",
    "ChatResponse",
    "CheckVoiceChatResponse",
    "ControlSessionMetadata",
    "Conversation",
    "CurrencyItem",
    "EmoteEvent",
    "EmoteResponse",
    "Error",
    "FloorHitResponse",
    "GetBackpackResponse",
    "GetConversationsResponse",
    "GetInventoryResponse",
    "GetMessagesResponse",
    "GetRoomPrivilegeResponse",
    "GetRoomUsersResponse",
    "GetUserOutfitResponse",
    "GetWalletResponse",
    "Highrise",
    "IndicatorResponse",
    "InstanceStartedEvent",
    "InstanceStoppedEvent",
    "InviteSpeakerResponse",
    "Item",
    "KeepaliveResponse",
    "LeaveConversationResponse",
    "Message",
    "MessageEvent",
    "MessageMedia",
    "MessageMediaResponse",
    "ModerateRoomResponse",
    "MoveUserToRoomResponse",
    "Position",
    "ReactionEvent",
    "ReactionResponse",
    "RemoveSpeakerResponse",
    "ResponseError",
    "RoomInfo",
    "RoomModeratedEvent",
    "RoomPermissions",
    "SendBulkMessageResponse",
    "SendMessageResponse",
    "SessionMetadata",
    "SetOutfitResponse",
    "TeleportResponse",
    "TipReactionEvent",
    "TipUserResponse",
    "User",
    "UserJoinedEvent",
    "UserLeftEvent",
    "UserMovedEvent",
    "VoiceEvent",
    "WebAPI",
    "bot_runner",
    "control_runner",
    "gather_subscriptions",
    "get_encoder_for",
    "get_sdk_module",
    "health",
    "install",
    "reset_stats",
    "stats",
]

# ---------------------------------------------------------------------------
# Constants / environment
# ---------------------------------------------------------------------------
KEEPALIVE_RATE = 15
READ_TIMEOUT = 20

SDK_NAME = "highrise-python-bot-sdk"
VERSION = __version__
USER_AGENT = os.environ.get("HR_SDK_USER_AGENT", f"{SDK_NAME}/{VERSION}")
BASE_WS_URL = os.environ.get(
    "HR_BOTAPI_URL",
    "wss://highrise.game/web/botapi",
).rstrip("/")
BASE_WEB_URL = os.environ.get(
    "HR_WEBAPI_URL",
    "https://webapi.highrise.game",
).rstrip("/")

try:
    _REQ_TIMEOUT = float(
        os.environ.get(
            "SDK_FAST_REQ_TIMEOUT", os.environ.get("HR_SDK_REQ_TIMEOUT", "0")
        )
        or 0
    )
except (TypeError, ValueError):
    _REQ_TIMEOUT = 0.0

_FIRE_AND_FORGET = os.environ.get("HR_FAST_FIRE_AND_FORGET", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

CLOSE_TYPES = {WSMsgType.CLOSE, WSMsgType.CLOSED}
if hasattr(WSMsgType, "CLOSING"):
    CLOSE_TYPES.add(WSMsgType.CLOSING)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger("highrise.fast")

# ---------------------------------------------------------------------------
# sdk_fast compatible stats
# ---------------------------------------------------------------------------
_STATS: dict[str, int] = {
    "fast": 0,
    "slow": 0,
    "errors": 0,
    "encode_errors": 0,
    "send_errors": 0,
    "timeouts": 0,
    "api_errors": 0,
    "fast_fallbacks": 0,
    "bytes_sent": 0,
    "pops": 0,
    "cleanups": 0,
    "incoming_calls": 0,
    "incoming_fast": 0,
    "incoming_slow": 0,
    "incoming_fallback": 0,
}
_LATENCIES_MS: deque[float] = deque(maxlen=10_000)


def _record_latency(t0: float) -> None:
    try:
        _LATENCIES_MS.append((time.perf_counter() - t0) * 1000.0)
    except (TypeError, ValueError):
        log.debug("Failed to record latency", exc_info=True)


def _latency_snapshot() -> dict[str, Any] | None:
    if not _LATENCIES_MS:
        return None
    arr = sorted(_LATENCIES_MS)
    n = len(arr)

    def pct(p: float) -> float:
        idx = int(n * p)
        idx = min(max(idx, 0), n - 1)
        return round(arr[idx], 3)

    return {
        "count": n,
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "max": round(arr[-1], 3),
    }


def stats() -> dict[str, Any]:
    successful_sends = _STATS["fast"] + _STATS["slow"]
    encoder_hit_rate = (
        round(_STATS["fast"] / successful_sends, 4) if successful_sends else None
    )
    incoming_rate = (
        round(_STATS["incoming_fast"] / _STATS["incoming_calls"], 4)
        if _STATS["incoming_calls"]
        else None
    )
    return {
        **_STATS,
        "incoming_fast_hits": _STATS["incoming_fast"],
        "encoder_hit_rate": encoder_hit_rate,
        "incoming_fast_rate": incoming_rate,
        "latency": _latency_snapshot(),
        "fast_enabled": True,
        "installed": True,
        "sdk_module": "highrise_fast",
        "outgoing_encoders": [
            "ChatRequest",
            "EmoteRequest",
            "ReactionRequest",
            "IndicatorRequest",
            "ChannelRequest",
            "FloorHitRequest",
            "AnchorHitRequest",
            "TeleportRequest",
            "GetRoomUsersRequest",
            "GetWalletRequest",
            "GetBackpackRequest",
            "ChangeBackpackRequest",
            "ModerateRoomRequest",
            "GetRoomPrivilegeRequest",
            "ChangeRoomPrivilegeRequest",
            "MoveUserToRoomRequest",
            "CheckVoiceChatRequest",
            "InviteSpeakerRequest",
            "RemoveSpeakerRequest",
            "GetUserOutfitRequest",
            "GetConversationsRequest",
            "SendMessageRequest",
            "SendBulkMessageRequest",
            "GetMessagesRequest",
            "LeaveConversationRequest",
            "BuyVoiceTimeRequest",
            "BuyRoomBoostRequest",
            "TipUserRequest",
            "GetInventoryRequest",
            "SetOutfitRequest",
            "BuyItemRequest",
            "MessageMediaRequest",
            "KeepaliveRequest",
        ],
        "incoming_hooks": [
            "Error",
            "ChatEvent",
            "EmoteEvent",
            "ReactionEvent",
            "UserJoinedEvent",
            "UserLeftEvent",
            "ChannelEvent",
            "TipReactionEvent",
            "UserMovedEvent",
            "VoiceEvent",
            "MessageEvent",
            "RoomModeratedEvent",
        ],
    }


def health() -> str:
    snap = stats()
    parts = ["leak-fix OK", "standalone SDK"]
    if snap.get("encoder_hit_rate") is not None:
        parts.append(f"outgoing hit-rate {snap['encoder_hit_rate'] * 100:.1f}%")
    if snap.get("incoming_fast_rate") is not None:
        parts.append(f"incoming fast-rate {snap['incoming_fast_rate'] * 100:.1f}%")
    if _REQ_TIMEOUT > 0:
        parts.append(f"timeout {_REQ_TIMEOUT}s")
    if _FIRE_AND_FORGET:
        parts.append("fire-and-forget enabled")
    return "sdk_fast: " + ", ".join(parts)


def reset_stats() -> None:
    for key in list(_STATS.keys()):
        _STATS[key] = 0
    _LATENCIES_MS.clear()


def install(verbose: bool = True) -> bool:
    if verbose:
        log.info("sdk_fast compatibility layer active in highrise_fast")
    return True


def get_sdk_module():
    return sys.modules.get("highrise_fast")


def get_encoder_for(cls):
    return None


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------
def _json_default(obj: Any) -> Any:
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, Item):
        return {
            "type": obj.type,
            "amount": obj.amount,
            "id": obj.id,
            "account_bound": obj.account_bound,
            "active_palette": obj.active_palette,
        }
    raise TypeError(f"Unsupported type for JSON encoding: {type(obj)!r}")


def dumps_json(payload: dict[str, Any]) -> bytes:
    if orjson is not None:
        return orjson.dumps(payload, default=_json_default)
    return json.dumps(
        payload,
        default=_json_default,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def loads_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if orjson is not None:
        return orjson.loads(raw)
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return json.loads(raw)


async def _ws_send_bytes(ws: Any, data: bytes) -> None:
    send_bytes = getattr(ws, "send_bytes", None)
    if callable(send_bytes):
        await send_bytes(data)
        return
    send_str = getattr(ws, "send_str", None)
    if callable(send_str):
        await send_str(data.decode("utf-8"))
        return
    raise TypeError("WebSocket object supports neither send_bytes nor send_str")


async def _send_ws_payload(ws: Any, payload: dict[str, Any]) -> None:
    try:
        if orjson is not None:
            data = orjson.dumps(payload, default=_json_default)
            _STATS["fast"] += 1
        else:
            data = json.dumps(
                payload,
                default=_json_default,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            _STATS["slow"] += 1
    except (TypeError, ValueError) as exc:
        _STATS["encode_errors"] += 1
        _STATS["errors"] += 1
        raise TypeError("JSON encoding failed") from exc

    try:
        await _ws_send_bytes(ws, data)
    except (ConnectionError, OSError, RuntimeError) as exc:
        _STATS["send_errors"] += 1
        _STATS["errors"] += 1
        raise ConnectionError("WebSocket send failed") from exc

    _STATS["bytes_sent"] += len(data)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class ResponseError(Exception):
    """An API response error."""


class _DoNotReconnect(Exception):
    """Internal exception used to stop reconnecting."""


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------
@dataclass
class User:
    id: str
    username: str


@dataclass
class Position:
    x: float
    y: float
    z: float
    facing: str = "FrontRight"


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

    __slots__ = (
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
            f"account_bound={self.account_bound!r},"
            f" active_palette={self.active_palette!r})"
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
            f"Message(message_id={self.message_id!r},"
            f" conversation_id={self.conversation_id!r},"
            f" sender_id={self.sender_id!r}, content={self.content[:40]!r})"
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
        self,
        message: str = "",
        do_not_reconnect: bool = False,
        rid: str | None = None,
    ) -> None:
        self.message = message
        self.do_not_reconnect = do_not_reconnect
        self.rid = rid

    def __repr__(self) -> str:
        return (
            f"Error(message={self.message!r}, "
            f"do_not_reconnect={self.do_not_reconnect!r}, rid={self.rid!r})"
        )


# ---------------------------------------------------------------------------
# Incoming event models
# ---------------------------------------------------------------------------
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
    reaction: str
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


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
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
    backpack: dict[str, int]
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


# ---------------------------------------------------------------------------
# Simple ack response models
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Control models
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------
def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_user(value: Any) -> User | None:
    if not isinstance(value, dict):
        return None
    return User(
        id=str(value.get("id", "")),
        username=str(value.get("username", "")),
    )


def parse_position(value: Any) -> Position | AnchorPosition | None:
    if not isinstance(value, dict):
        return None
    if "entity_id" in value or "anchor_ix" in value:
        return AnchorPosition(
            entity_id=str(value.get("entity_id", "")),
            anchor_ix=_as_int(value.get("anchor_ix"), 0),
        )
    return Position(
        x=_as_float(value.get("x"), 0.0),
        y=_as_float(value.get("y"), 0.0),
        z=_as_float(value.get("z"), 0.0),
        facing=str(value.get("facing", "FrontRight")),
    )


def parse_item(value: Any) -> Item | None:
    if not isinstance(value, dict):
        return None
    return Item(
        type=str(value.get("type", "clothing")),
        amount=_as_int(value.get("amount"), 1),
        id=str(value.get("id", "")),
        account_bound=bool(value.get("account_bound", False)),
        active_palette=value.get("active_palette"),
    )


def parse_currency(value: Any) -> CurrencyItem | None:
    if not isinstance(value, dict):
        return None
    return CurrencyItem(
        type=str(value.get("type", "")),
        amount=_as_int(value.get("amount"), 0),
    )


def parse_item_or_currency(value: Any) -> Item | CurrencyItem | None:
    if not isinstance(value, dict):
        return None
    if value.get("type") == "clothing":
        return parse_item(value)
    return parse_currency(value)


def parse_message(value: Any) -> Message | None:
    if not isinstance(value, dict):
        return None
    return Message(
        message_id=str(value.get("message_id", value.get("id", ""))),
        conversation_id=str(value.get("conversation_id", "")),
        createdAt=value.get("createdAt", value.get("created_at")),
        content=str(value.get("content", "")),
        sender_id=str(value.get("sender_id", value.get("user_id", ""))),
        category=str(value.get("category", "text")),
    )


def parse_conversation(value: Any) -> Conversation | None:
    if not isinstance(value, dict):
        return None
    last_message_raw = value.get("last_message")
    last_message = parse_message(last_message_raw) if last_message_raw else None
    return Conversation(
        id=str(value.get("id", "")),
        did_join=bool(value.get("did_join", False)),
        unread_count=_as_int(value.get("unread_count"), 0),
        last_message=last_message,
        muted=bool(value.get("muted", False)),
        member_ids=value.get("member_ids"),
        name=value.get("name"),
        owner_id=value.get("owner_id"),
    )


def parse_media(value: Any) -> MessageMedia | None:
    if not isinstance(value, dict):
        return None
    return MessageMedia(
        type=str(value.get("type", "image")),
        width=_as_int(value.get("width"), 0),
        height=_as_int(value.get("height"), 0),
        mediaSizeInBytes=_as_int(value.get("mediaSizeInBytes"), 0),
        thumbnailSizeInBytes=_as_int(value.get("thumbnailSizeInBytes"), 0),
        id=value.get("id"),
        url=value.get("url"),
        thumbnailUrl=value.get("thumbnailUrl"),
    )


def parse_session_metadata(data: dict[str, Any]) -> SessionMetadata:
    room_raw = data.get("room_info", {}) or {}
    room_info = RoomInfo(
        owner_id=str(room_raw.get("owner_id", "")),
        room_name=str(room_raw.get("room_name", "")),
    )
    return SessionMetadata(
        user_id=str(data.get("user_id", "")),
        room_info=room_info,
        rate_limits=data.get("rate_limits", {}) or {},
        connection_id=str(data.get("connection_id", "")),
        sdk_version=data.get("sdk_version"),
    )


def parse_control_session_metadata(data: dict[str, Any]) -> ControlSessionMetadata:
    return ControlSessionMetadata(
        connection_id=str(data.get("connection_id", "")),
        instance_ids=list(data.get("instance_ids", []) or []),
    )


def parse_server_message(data: dict[str, Any]) -> Any:
    """Parse responses and events from the server."""
    if not isinstance(data, dict):
        return data

    t = data.get("_type")
    rid = data.get("rid")

    if t == "Error":
        return Error(
            message=str(data.get("message", "")),
            do_not_reconnect=bool(data.get("do_not_reconnect", False)),
            rid=rid,
        )

    if t == "ChatEvent":
        return ChatEvent(
            user=parse_user(data.get("user")) or User(id="", username=""),
            message=str(data.get("message", "")),
            whisper=bool(data.get("whisper", False)),
        )

    if t == "EmoteEvent":
        return EmoteEvent(
            user=parse_user(data.get("user")) or User(id="", username=""),
            emote_id=str(data.get("emote_id", "")),
            receiver=parse_user(data.get("receiver")),
        )

    if t == "ReactionEvent":
        return ReactionEvent(
            user=parse_user(data.get("user")) or User(id="", username=""),
            reaction=str(data.get("reaction", "")),
            receiver=parse_user(data.get("receiver")),
        )

    if t == "UserJoinedEvent":
        return UserJoinedEvent(
            user=parse_user(data.get("user")) or User(id="", username=""),
            position=parse_position(data.get("position")),
        )

    if t == "UserLeftEvent":
        return UserLeftEvent(
            user=parse_user(data.get("user")) or User(id="", username=""),
        )

    if t == "ChannelEvent":
        return ChannelEvent(
            sender_id=str(data.get("sender_id", "")),
            msg=str(data.get("msg", "")),
            tags=list(data.get("tags", []) or []),
        )

    if t == "TipReactionEvent":
        return TipReactionEvent(
            sender=parse_user(data.get("sender")) or User(id="", username=""),
            receiver=parse_user(data.get("receiver")) or User(id="", username=""),
            item=parse_item_or_currency(data.get("item")),
        )

    if t == "UserMovedEvent":
        return UserMovedEvent(
            user=parse_user(data.get("user")) or User(id="", username=""),
            position=parse_position(data.get("position")),
        )

    if t == "VoiceEvent":
        raw_users = data.get("users", []) or []
        users: list[tuple[User, str]] = []
        for pair in raw_users:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                u = parse_user(pair[0])
                if u is not None:
                    users.append((u, str(pair[1])))
        return VoiceEvent(
            users=users,
            seconds_left=_as_int(data.get("seconds_left"), 0),
        )

    if t == "MessageEvent":
        return MessageEvent(
            user_id=str(data.get("user_id", "")),
            conversation_id=str(data.get("conversation_id", "")),
            is_new_conversation=bool(data.get("is_new_conversation", False)),
        )

    if t == "RoomModeratedEvent":
        duration_raw = data.get("duration")
        return RoomModeratedEvent(
            moderatorId=str(data.get("moderatorId", "")),
            targetUserId=str(data.get("targetUserId", "")),
            moderationType=str(data.get("moderationType", "")),
            duration=None if duration_raw is None else _as_int(duration_raw),
        )

    if t == "GetRoomUsersResponse":
        content: list[tuple[User, Position | AnchorPosition]] = []
        for row in data.get("content", []) or []:
            if isinstance(row, (list, tuple)) and len(row) == 2:
                user = parse_user(row[0])
                pos = parse_position(row[1])
                if user is not None and pos is not None:
                    content.append((user, pos))
        return GetRoomUsersResponse(content=content, rid=rid)

    if t == "GetWalletResponse":
        content_wallet = []
        for entry in data.get("content", []) or []:
            cur = parse_currency(entry)
            if cur is not None:
                content_wallet.append(cur)
        return GetWalletResponse(content=content_wallet, rid=rid)

    if t == "GetBackpackResponse":
        backpack = data.get("backpack", {}) or {}
        if not isinstance(backpack, dict):
            backpack = {}
        return GetBackpackResponse(backpack=backpack, rid=rid)

    if t == "ChangeBackpackResponse":
        return ChangeBackpackResponse(rid=rid)

    if t == "GetRoomPrivilegeResponse":
        content_raw = data.get("content", {}) or {}
        return GetRoomPrivilegeResponse(
            content=RoomPermissions(
                moderator=content_raw.get("moderator"),
                designer=content_raw.get("designer"),
            ),
            rid=rid,
        )

    if t == "CheckVoiceChatResponse":
        return CheckVoiceChatResponse(
            seconds_left=_as_int(data.get("seconds_left"), 0),
            auto_speakers=set(data.get("auto_speakers", []) or []),
            users=dict(data.get("users", {}) or {}),
            rid=rid,
        )

    if t == "GetUserOutfitResponse":
        outfit: list[Item] = []
        for raw_item in data.get("outfit", []) or []:
            item = parse_item(raw_item)
            if item is not None:
                outfit.append(item)
        return GetUserOutfitResponse(outfit=outfit, rid=rid)

    if t == "GetConversationsResponse":
        conversations: list[Conversation] = []
        for raw_conv in data.get("conversations", []) or []:
            conv = parse_conversation(raw_conv)
            if conv is not None:
                conversations.append(conv)
        return GetConversationsResponse(
            conversations=conversations,
            not_joined=_as_int(data.get("not_joined"), 0),
            rid=rid,
        )

    if t == "SendMessageResponse":
        return SendMessageResponse(rid=rid)

    if t == "SendBulkMessageResponse":
        return SendBulkMessageResponse(rid=rid)

    if t == "GetMessagesResponse":
        messages: list[Message] = []
        for raw_msg in data.get("messages", []) or []:
            msg = parse_message(raw_msg)
            if msg is not None:
                messages.append(msg)
        return GetMessagesResponse(messages=messages, rid=rid)

    if t == "LeaveConversationResponse":
        return LeaveConversationResponse(rid=rid)

    if t == "BuyVoiceTimeResponse":
        return BuyVoiceTimeResponse(result=str(data.get("result", "")), rid=rid)

    if t == "BuyRoomBoostResponse":
        return BuyRoomBoostResponse(result=str(data.get("result", "")), rid=rid)

    if t == "TipUserResponse":
        return TipUserResponse(result=str(data.get("result", "")), rid=rid)

    if t == "GetInventoryResponse":
        items: list[Item] = []
        for raw_item in data.get("items", []) or []:
            item = parse_item(raw_item)
            if item is not None:
                items.append(item)
        return GetInventoryResponse(items=items, rid=rid)

    if t == "SetOutfitResponse":
        return SetOutfitResponse(rid=rid)

    if t == "BuyItemResponse":
        return BuyItemResponse(result=str(data.get("result", "")), rid=rid)

    if t == "MessageMediaResponse":
        return MessageMediaResponse(
            media=parse_media(data.get("media")),
            uploadUrl=data.get("uploadUrl"),
            thumbnailUploadUrl=data.get("thumbnailUploadUrl"),
            rid=rid,
        )

    _ACK_MAP = {
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
    ack_cls = _ACK_MAP.get(t)
    if ack_cls is not None:
        return ack_cls(rid=rid)

    return types.SimpleNamespace(**data)


# ---------------------------------------------------------------------------
# Wire conversion helpers
# ---------------------------------------------------------------------------
def position_to_wire(pos: Any) -> dict[str, Any]:
    if pos is None:
        raise ValueError("Position cannot be None")
    if isinstance(pos, AnchorPosition):
        return {"entity_id": pos.entity_id, "anchor_ix": pos.anchor_ix}
    if isinstance(pos, Position):
        return {"x": pos.x, "y": pos.y, "z": pos.z, "facing": pos.facing}
    if isinstance(pos, dict):
        if "entity_id" in pos or "anchor_ix" in pos:
            return {
                "entity_id": pos.get("entity_id"),
                "anchor_ix": _as_int(pos.get("anchor_ix"), 0),
            }
        return {
            "x": _as_float(pos.get("x"), 0.0),
            "y": _as_float(pos.get("y"), 0.0),
            "z": _as_float(pos.get("z"), 0.0),
            "facing": str(pos.get("facing", "FrontRight")),
        }
    raise TypeError(f"Unsupported position type: {type(pos)!r}")


def item_to_wire(item: Any) -> dict[str, Any]:
    if item is None:
        raise ValueError("Item cannot be None")
    if isinstance(item, Item):
        return {
            "type": item.type,
            "amount": item.amount,
            "id": item.id,
            "account_bound": item.account_bound,
            "active_palette": item.active_palette,
        }
    if isinstance(item, dict):
        return {
            "type": item.get("type", "clothing"),
            "amount": _as_int(item.get("amount"), 1),
            "id": str(item.get("id", "")),
            "account_bound": bool(item.get("account_bound", False)),
            "active_palette": item.get("active_palette"),
        }
    raise TypeError(f"Unsupported item type: {type(item)!r}")


def permissions_to_wire(permissions: Any) -> dict[str, Any]:
    if permissions is None:
        return {"moderator": None, "designer": None}
    if isinstance(permissions, RoomPermissions):
        return {"moderator": permissions.moderator, "designer": permissions.designer}
    if isinstance(permissions, dict):
        return permissions
    raise TypeError(f"Unsupported permissions type: {type(permissions)!r}")


def media_to_wire(media: Any) -> dict[str, Any]:
    if media is None:
        raise ValueError("Media cannot be None")
    if isinstance(media, MessageMedia):
        return {
            "type": media.type,
            "width": media.width,
            "height": media.height,
            "mediaSizeInBytes": media.mediaSizeInBytes,
            "thumbnailSizeInBytes": media.thumbnailSizeInBytes,
            "id": media.id,
            "url": media.url,
            "thumbnailUrl": media.thumbnailUrl,
        }
    if isinstance(media, dict):
        return media
    raise TypeError(f"Unsupported media type: {type(media)!r}")


# ---------------------------------------------------------------------------
# BaseBot
# ---------------------------------------------------------------------------
class BaseBot:
    """Compatible Highrise BaseBot."""

    highrise: Highrise
    webapi: WebAPI

    async def before_start(self, tg: TaskGroup) -> None:
        pass

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        pass

    async def on_chat(self, user: User, message: str) -> None:
        pass

    async def on_whisper(self, user: User, message: str) -> None:
        pass

    async def on_emote(self, user: User, emote_id: str, receiver: User | None) -> None:
        pass

    async def on_reaction(self, user: User, reaction: str, receiver: User) -> None:
        pass

    async def on_user_join(
        self, user: User, position: Position | AnchorPosition
    ) -> None:
        pass

    async def on_user_leave(self, user: User) -> None:
        pass

    async def on_tip(
        self, sender: User, receiver: User, tip: CurrencyItem | Item
    ) -> None:
        pass

    async def on_channel(self, sender_id: str, message: str, tags: set[str]) -> None:
        pass

    async def on_user_move(
        self, user: User, destination: Position | AnchorPosition
    ) -> None:
        pass

    async def on_voice_change(
        self,
        users: list[tuple[User, Literal["voice", "muted"]]],
        seconds_left: int,
    ) -> None:
        pass

    async def on_message(
        self, user_id: str, conversation_id: str, is_new_conversation: bool
    ) -> None:
        pass

    async def on_moderate(
        self,
        moderator_id: str,
        target_user_id: str,
        moderation_type: Literal["kick", "mute", "unmute", "ban", "unban"],
        duration: int | None,
    ) -> None:
        pass


# ---------------------------------------------------------------------------
# Highrise websocket API
# ---------------------------------------------------------------------------
class Highrise:
    """Standalone Highrise request API."""

    def __init__(
        self,
        ws: Any = None,
        tg: TaskGroup | None = None,
        my_id: str = "",
    ) -> None:
        self.ws = ws
        self.tg = tg
        self.my_id = my_id
        self._req_id = count()
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._req_id_registry = self._pending

    def _next_rid(self) -> str:
        return str(next(self._req_id))

    def _resolve_pending(self, rid: str, data: dict[str, Any]) -> bool:
        future = self._pending.pop(rid, None)
        if future is not None and not future.done():
            obj = parse_server_message(data)
            future.set_result(obj)
            return True
        return False

    async def _send_only(
        self, type_name: str, fields: dict[str, Any] | None = None
    ) -> None:
        payload: dict[str, Any] = {"_type": type_name, "rid": self._next_rid()}
        if fields:
            payload.update(fields)
        await _send_ws_payload(self.ws, payload)

    async def _call(
        self,
        type_name: str,
        fields: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
        raise_on_error: bool = False,
    ) -> Any:
        rid = self._next_rid()
        payload: dict[str, Any] = {"_type": type_name, "rid": rid}
        if fields:
            payload.update(fields)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[rid] = future
        t0 = time.perf_counter()

        try:
            await _send_ws_payload(self.ws, payload)
            effective_timeout = timeout if timeout is not None else _REQ_TIMEOUT
            if effective_timeout > 0:
                response = await asyncio.wait_for(future, timeout=effective_timeout)
            else:
                response = await future
            _STATS["pops"] += 1
            _record_latency(t0)
            if isinstance(response, Error):
                _STATS["api_errors"] += 1
            if raise_on_error and isinstance(response, Error):
                raise ResponseError(response.message)
            return response
        except TimeoutError:
            _STATS["timeouts"] += 1
            raise
        finally:
            self._pending.pop(rid, None)
            _STATS["cleanups"] += 1

    async def _no_response(
        self, type_name: str, fields: dict[str, Any] | None = None
    ) -> None:
        if _FIRE_AND_FORGET:
            await self._send_only(type_name, fields)
        else:
            await self._call(type_name, fields, raise_on_error=True)

    # -- Chat / social ------------------------------------------------

    async def chat(self, message: str) -> None:
        await self._no_response(
            "ChatRequest",
            {"message": message, "whisper_target_id": None},
        )

    async def send_whisper(self, user_id: str, message: str) -> None:
        await self._no_response(
            "ChatRequest",
            {"message": message, "whisper_target_id": user_id},
        )

    async def send_emote(
        self, emote_id: str, target_user_id: str | None = None
    ) -> None:
        await self._no_response(
            "EmoteRequest",
            {"emote_id": emote_id, "target_user_id": target_user_id},
        )

    async def react(self, reaction: str, target_user_id: str) -> None:
        await self._no_response(
            "ReactionRequest",
            {"reaction": reaction, "target_user_id": target_user_id},
        )

    async def set_indicator(self, icon: str | None) -> None:
        await self._no_response("IndicatorRequest", {"icon": icon})

    async def send_channel(
        self,
        message: str,
        tags: set[str] | list[str] | tuple[str, ...] | None = None,
        only_to: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> None:
        await self._no_response(
            "ChannelRequest",
            {
                "message": message,
                "tags": list(tags or []),
                "only_to": list(only_to) if only_to is not None else None,
            },
        )

    # -- Movement -----------------------------------------------------

    async def walk_to(
        self, destination: Position | AnchorPosition | dict[str, Any]
    ) -> None:
        wire = position_to_wire(destination)
        if isinstance(destination, AnchorPosition) or (
            isinstance(destination, dict)
            and ("entity_id" in destination or "anchor_ix" in destination)
        ):
            await self._no_response("AnchorHitRequest", {"anchor": wire})
        else:
            await self._no_response("FloorHitRequest", {"destination": wire})

    async def teleport(self, user_id: str, dest: Position | dict[str, Any]) -> None:
        await self._no_response(
            "TeleportRequest",
            {"user_id": user_id, "destination": position_to_wire(dest)},
        )

    # -- Room queries -------------------------------------------------

    async def get_room_users(self) -> GetRoomUsersResponse | Error:
        return await self._call("GetRoomUsersRequest", {})

    async def get_wallet(self) -> GetWalletResponse | Error:
        return await self._call("GetWalletRequest", {})

    async def get_backpack(self, user_id: str) -> GetBackpackResponse | Error:
        return await self._call("GetBackpackRequest", {"user_id": user_id})

    async def change_backpack(
        self, user_id: str, changes: dict[str, int]
    ) -> ChangeBackpackResponse | Error:
        return await self._call(
            "ChangeBackpackRequest",
            {"user_id": user_id, "changes": dict(changes)},
        )

    # -- Moderation / privileges --------------------------------------

    async def moderate_room(
        self,
        user_id: str,
        action: Literal["kick", "ban", "unban", "mute"],
        action_length: int | None = None,
    ) -> None:
        await self._no_response(
            "ModerateRoomRequest",
            {
                "user_id": user_id,
                "moderation_action": action,
                "action_length": action_length,
            },
        )

    async def get_room_privilege(self, user_id: str) -> RoomPermissions | Error:
        response = await self._call("GetRoomPrivilegeRequest", {"user_id": user_id})
        if isinstance(response, Error):
            return response
        return getattr(response, "content", RoomPermissions())

    async def change_room_privilege(
        self, user_id: str, permissions: RoomPermissions | dict[str, Any]
    ) -> None:
        await self._no_response(
            "ChangeRoomPrivilegeRequest",
            {"user_id": user_id, "permissions": permissions_to_wire(permissions)},
        )

    async def move_user_to_room(self, user_id: str, room_id: str) -> None:
        await self._no_response(
            "MoveUserToRoomRequest",
            {"user_id": user_id, "room_id": room_id},
        )

    # -- Voice --------------------------------------------------------

    async def get_voice_status(self) -> CheckVoiceChatResponse | Error:
        return await self._call("CheckVoiceChatRequest", {})

    async def add_user_to_voice(self, user_id: str) -> None:
        await self._no_response("InviteSpeakerRequest", {"user_id": user_id})

    async def remove_user_from_voice(self, user_id: str) -> None:
        await self._no_response("RemoveSpeakerRequest", {"user_id": user_id})

    # -- Outfits / inventory ------------------------------------------

    async def get_user_outfit(self, user_id: str) -> GetUserOutfitResponse | Error:
        return await self._call("GetUserOutfitRequest", {"user_id": user_id})

    async def get_my_outfit(self) -> GetUserOutfitResponse | Error:
        return await self.get_user_outfit(self.my_id)

    async def get_inventory(self) -> GetInventoryResponse | Error:
        return await self._call("GetInventoryRequest", {})

    async def set_outfit(self, outfit: list[Item | dict[str, Any]]) -> None | Error:
        response = await self._call(
            "SetOutfitRequest",
            {"outfit": [item_to_wire(item) for item in outfit]},
        )
        if isinstance(response, Error):
            return response
        return None

    async def buy_item(self, item_id: str) -> str | Error:
        response = await self._call("BuyItemRequest", {"item_id": item_id})
        if isinstance(response, Error):
            return response
        return getattr(response, "result", "")

    # -- Inbox / conversations ----------------------------------------

    async def get_conversations(
        self, not_joined: bool = False, last_id: str | None = None
    ) -> GetConversationsResponse | Error:
        return await self._call(
            "GetConversationsRequest",
            {"not_joined": not_joined, "last_id": last_id},
        )

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        message_type: Literal["text", "invite", "media"] = "text",
        room_id: str | None = None,
        world_id: str | None = None,
        media_id: str | None = None,
    ) -> None | Error:
        response = await self._call(
            "SendMessageRequest",
            {
                "conversation_id": conversation_id,
                "content": content,
                "type": message_type,
                "room_id": room_id,
                "world_id": world_id,
                "media_id": media_id,
            },
        )
        if isinstance(response, Error):
            return response
        return None

    async def send_message_bulk(
        self,
        user_ids: list[str],
        content: str,
        message_type: Literal["text", "invite"] = "text",
        room_id: str | None = None,
        world_id: str | None = None,
    ) -> None | Error:
        response = await self._call(
            "SendBulkMessageRequest",
            {
                "user_ids": user_ids,
                "content": content,
                "type": message_type,
                "room_id": room_id,
                "world_id": world_id,
            },
        )
        if isinstance(response, Error):
            return response
        return None

    async def get_messages(
        self, conversation_id: str, last_id: str | None = None
    ) -> GetMessagesResponse | Error:
        return await self._call(
            "GetMessagesRequest",
            {"conversation_id": conversation_id, "last_message_id": last_id},
        )

    async def leave_conversation(self, conversation_id: str) -> None:
        await self._no_response(
            "LeaveConversationRequest", {"conversation_id": conversation_id}
        )

    # -- Economy ------------------------------------------------------

    async def buy_voice_time(
        self, payment: Literal["bot_wallet_only"] = "bot_wallet_only"
    ) -> str | Error:
        response = await self._call("BuyVoiceTimeRequest", {"payment_method": payment})
        if isinstance(response, Error):
            return response
        return getattr(response, "result", "")

    async def buy_room_boost(
        self,
        payment: Literal["bot_wallet_only"] = "bot_wallet_only",
        amount: int = 1,
    ) -> str | Error:
        response = await self._call(
            "BuyRoomBoostRequest",
            {"payment_method": payment, "amount": amount},
        )
        if isinstance(response, Error):
            return response
        return getattr(response, "result", "")

    async def tip_user(
        self,
        user_id: str,
        tip: Literal[
            "gold_bar_1",
            "gold_bar_5",
            "gold_bar_10",
            "gold_bar_50",
            "gold_bar_100",
            "gold_bar_500",
            "gold_bar_1k",
            "gold_bar_5000",
            "gold_bar_10k",
        ],
    ) -> str | Error:
        response = await self._call(
            "TipUserRequest", {"user_id": user_id, "gold_bar": tip}
        )
        if isinstance(response, Error):
            return response
        return getattr(response, "result", "")

    # -- Media --------------------------------------------------------

    async def message_media_upload(
        self, media: MessageMedia | dict[str, Any]
    ) -> tuple[MessageMedia | None, str | None, str | None] | Error:
        response = await self._call(
            "MessageMediaRequest", {"media": media_to_wire(media)}
        )
        if isinstance(response, Error):
            return response
        return (
            getattr(response, "media", None),
            getattr(response, "uploadUrl", None),
            getattr(response, "thumbnailUploadUrl", None),
        )

    # -- Utility ------------------------------------------------------

    def call_in(self, callback: Callable[[], Any], delay: float) -> None:
        async def _delayed() -> None:
            await asyncio.sleep(delay)
            try:
                result = callback()
                if isawaitable(result):
                    await result
            except (RuntimeError, ValueError, TypeError):
                log.exception("Error in delayed callback")

        if self.tg is not None:
            self.tg.create_task(_delayed())
        else:
            asyncio.create_task(_delayed())


# ---------------------------------------------------------------------------
# WebAPI
# ---------------------------------------------------------------------------
class WebAPI:
    """Lightweight WebAPI client."""

    def __init__(self, base_url: str = BASE_WEB_URL) -> None:
        self.url = base_url.rstrip("/")

    async def _get(self, endpoint: str) -> Any:
        async with (
            ClientSession() as session,
            session.get(f"{self.url}{endpoint}") as response,
        ):
            if response.status == 200:
                return loads_json(await response.read())
            raise ResponseError((await response.read()).decode())

    @staticmethod
    def _query(params: dict[str, Any]) -> str:
        clean: dict[str, Any] = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                clean[key] = "true" if value else "false"
            else:
                clean[key] = value
        if not clean:
            return ""
        parts = [f"{k}={v}" for k, v in clean.items()]
        return "?" + "&".join(parts)

    async def get_user(self, user_id: str) -> Any:
        return await self._get(f"/users/{user_id}")

    async def get_users(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        username: str | None = None,
    ) -> Any:
        return await self._get(
            "/users"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "username": username,
                }
            )
        )

    async def get_room(self, room_id: str) -> Any:
        return await self._get(f"/rooms/{room_id}")

    async def get_rooms(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        room_name: str | None = None,
        owner_id: str | None = None,
    ) -> Any:
        return await self._get(
            "/rooms"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "room_name": room_name,
                    "owner_id": owner_id,
                }
            )
        )

    async def get_post(self, post_id: str) -> Any:
        return await self._get(f"/posts/{post_id}")

    async def get_posts(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        author_id: str | None = None,
    ) -> Any:
        return await self._get(
            "/posts"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "author_id": author_id,
                }
            )
        )

    async def get_item(self, item_id: str) -> Any:
        return await self._get(f"/items/{item_id}")

    async def get_items(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        rarity: str | None = None,
        item_name: str | None = None,
        category: Any | None = None,
    ) -> Any:
        category_value = getattr(category, "value", category)
        return await self._get(
            "/items"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "rarity": rarity,
                    "item_name": item_name,
                    "category": category_value,
                }
            )
        )

    async def get_grab(self, grab_id: str) -> Any:
        return await self._get(f"/grabs/{grab_id}")

    async def get_grabs(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: str = "desc",
        limit: int = 20,
        title: str | None = None,
    ) -> Any:
        return await self._get(
            "/grabs"
            + self._query(
                {
                    "starts_after": starts_after,
                    "ends_before": ends_before,
                    "sort_order": sort_order,
                    "limit": limit,
                    "title": title,
                }
            )
        )


# ---------------------------------------------------------------------------
# Event subscriptions
# ---------------------------------------------------------------------------
def gather_subscriptions(bot: BaseBot) -> str:
    method_map: dict[str, str] = {
        "on_chat": "chat",
        "on_whisper": "chat",
        "on_emote": "emote",
        "on_reaction": "reaction",
        "on_user_join": "user_joined",
        "on_user_leave": "user_left",
        "on_user_move": "user_moved",
        "on_tip": "tip_reaction",
        "on_voice_change": "voice",
        "on_channel": "channel",
        "on_message": "message",
        "on_moderate": "moderation",
    }
    subscriptions: set[str] = set()
    for method_name, event_name in method_map.items():
        base_handler = getattr(BaseBot, method_name, None)
        bot_handler = getattr(type(bot), method_name, None)
        if bot_handler is not None and bot_handler is not base_handler:
            subscriptions.add(event_name)
    if not subscriptions:
        return ""
    return "?events=" + ",".join(sorted(subscriptions))


# ---------------------------------------------------------------------------
# Safe handler spawning
# ---------------------------------------------------------------------------
async def _safe_handler(result: Any) -> None:
    try:
        if isawaitable(result):
            await result
    except (RuntimeError, ValueError, TypeError, KeyError, AttributeError):
        log.exception("Handler error")


def _spawn_task(tg: TaskGroup, result: Any) -> None:
    tg.create_task(_safe_handler(result))


# ---------------------------------------------------------------------------
# Event dispatch
# ---------------------------------------------------------------------------
def _dispatch_event(
    bot: BaseBot,
    bot_id: str,
    event_type: str | None,
    data: dict[str, Any],
    tg: TaskGroup,
) -> None:
    if event_type == "ChatEvent":
        user = parse_user(data.get("user"))
        if user is None or user.id == bot_id:
            return
        message = str(data.get("message", ""))
        whisper = bool(data.get("whisper", False))
        if whisper:
            _spawn_task(tg, bot.on_whisper(user, message))
        else:
            _spawn_task(tg, bot.on_chat(user, message))

    elif event_type == "EmoteEvent":
        user = parse_user(data.get("user"))
        if user is None:
            return
        receiver = parse_user(data.get("receiver"))
        _spawn_task(tg, bot.on_emote(user, str(data.get("emote_id", "")), receiver))

    elif event_type == "ReactionEvent":
        user = parse_user(data.get("user"))
        receiver = parse_user(data.get("receiver"))
        if user is None or receiver is None:
            return
        _spawn_task(tg, bot.on_reaction(user, str(data.get("reaction", "")), receiver))

    elif event_type == "UserJoinedEvent":
        user = parse_user(data.get("user"))
        position = parse_position(data.get("position"))
        if user is None or position is None:
            return
        _spawn_task(tg, bot.on_user_join(user, position))

    elif event_type == "UserLeftEvent":
        user = parse_user(data.get("user"))
        if user is None:
            return
        _spawn_task(tg, bot.on_user_leave(user))

    elif event_type == "ChannelEvent":
        sender_id = str(data.get("sender_id", ""))
        message = str(data.get("msg", ""))
        tags = set(data.get("tags", []) or [])
        _spawn_task(tg, bot.on_channel(sender_id, message, tags))

    elif event_type == "TipReactionEvent":
        sender = parse_user(data.get("sender"))
        receiver = parse_user(data.get("receiver"))
        item = parse_item_or_currency(data.get("item"))
        if sender is None or receiver is None or item is None:
            return
        _spawn_task(tg, bot.on_tip(sender, receiver, item))

    elif event_type == "UserMovedEvent":
        user = parse_user(data.get("user"))
        position = parse_position(data.get("position"))
        if user is None or position is None:
            return
        _spawn_task(tg, bot.on_user_move(user, position))

    elif event_type == "VoiceEvent":
        raw_users = data.get("users", []) or []
        users: list[tuple[User, str]] = []
        for pair in raw_users:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                u = parse_user(pair[0])
                if u is not None:
                    users.append((u, str(pair[1])))
        seconds_left = _as_int(data.get("seconds_left"), 0)
        _spawn_task(tg, bot.on_voice_change(users, seconds_left))

    elif event_type == "MessageEvent":
        _spawn_task(
            tg,
            bot.on_message(
                str(data.get("user_id", "")),
                str(data.get("conversation_id", "")),
                bool(data.get("is_new_conversation", False)),
            ),
        )

    elif event_type == "RoomModeratedEvent":
        duration_raw = data.get("duration")
        duration = None if duration_raw is None else _as_int(duration_raw)
        _spawn_task(
            tg,
            bot.on_moderate(
                str(data.get("moderatorId", "")),
                str(data.get("targetUserId", "")),
                str(data.get("moderationType", "")),
                duration,
            ),
        )

    else:
        _STATS["incoming_fallback"] += 1


# ---------------------------------------------------------------------------
# Receive helpers
# ---------------------------------------------------------------------------
async def _receive_metadata(ws: Any) -> SessionMetadata | Error:
    frame = await ws.receive(READ_TIMEOUT)
    if frame.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
        raise ConnectionResetError("No valid session metadata")
    data = loads_json(frame.data)
    if not isinstance(data, dict):
        raise ConnectionResetError("Invalid session metadata payload")
    if data.get("_type") == "Error":
        return Error(
            message=str(data.get("message", "")),
            do_not_reconnect=bool(data.get("do_not_reconnect", False)),
            rid=data.get("rid"),
        )
    return parse_session_metadata(data)


async def _receive_control_metadata(ws: Any) -> ControlSessionMetadata | Error:
    frame = await ws.receive(READ_TIMEOUT)
    if frame.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
        raise ConnectionResetError("No valid control metadata")
    data = loads_json(frame.data)
    if not isinstance(data, dict):
        raise ConnectionResetError("Invalid control metadata payload")
    if data.get("_type") == "Error":
        return Error(
            message=str(data.get("message", "")),
            do_not_reconnect=bool(data.get("do_not_reconnect", False)),
            rid=data.get("rid"),
        )
    return parse_control_session_metadata(data)


async def _send_keepalive(ws: Any) -> None:
    while True:
        await asyncio.sleep(KEEPALIVE_RATE)
        try:
            await _send_ws_payload(ws, {"_type": "KeepaliveRequest"})
        except (ConnectionError, OSError, RuntimeError):
            return


async def _receive_loop(
    ws: Any,
    highrise: Highrise,
    bot: BaseBot,
    tg: TaskGroup,
    session_metadata: SessionMetadata,
) -> None:
    bot_id = str(session_metadata.user_id)
    while True:
        frame = await ws.receive(READ_TIMEOUT)

        if frame.type in CLOSE_TYPES:
            print(
                f"Connection with ID: {session_metadata.connection_id} "
                "closed by server, reconnecting."
            )
            raise ConnectionResetError

        if frame.type == WSMsgType.ERROR:
            raise ConnectionResetError("WebSocket error")

        if frame.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
            continue
        if frame.data is None:
            continue

        try:
            data = loads_json(frame.data)
        except (ValueError, TypeError, UnicodeDecodeError):
            _STATS["incoming_fallback"] += 1
            continue

        if not isinstance(data, dict):
            _STATS["incoming_fallback"] += 1
            continue

        _STATS["incoming_calls"] += 1
        rid = data.get("rid")
        if isinstance(rid, str):
            if highrise._resolve_pending(rid, data):
                _STATS["incoming_fast"] += 1
                continue
            continue

        event_type = data.get("_type")

        if event_type == "Error":
            error = Error(
                message=str(data.get("message", "")),
                do_not_reconnect=bool(data.get("do_not_reconnect", False)),
                rid=data.get("rid"),
            )
            print(
                f"ERROR: {error.message} closing connection with ID: "
                f"{session_metadata.connection_id}"
            )
            if error.do_not_reconnect:
                raise _DoNotReconnect
            raise ConnectionResetError

        try:
            _dispatch_event(bot, bot_id, event_type, data, tg)
            _STATS["incoming_fast"] += 1
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError):
            _STATS["incoming_fallback"] += 1
            log.exception("Event dispatch failed")


# ---------------------------------------------------------------------------
# Throttler
# ---------------------------------------------------------------------------
async def throttler(drops: int = 5, drop_recharge: float = 5.0):
    """Simple reconnect throttler."""
    tokens = float(drops)
    last = time.monotonic()
    while True:
        now = time.monotonic()
        elapsed = now - last
        last = now
        tokens = min(float(drops), tokens + (elapsed / max(0.001, drop_recharge)))
        if tokens >= 1.0:
            tokens -= 1.0
            yield
        else:
            await asyncio.sleep((1.0 - tokens) * max(0.001, drop_recharge))
            last = time.monotonic()
            tokens = 0.0
            yield


# ---------------------------------------------------------------------------
# Bot runner
# ---------------------------------------------------------------------------
@dataclass
class BotDefinition:
    bot: BaseBot
    room_id: str
    api_token: str


async def bot_runner(bot: BaseBot, room_id: str, api_key: str) -> None:
    async with TaskGroup() as tg:
        t = throttler(5, 5)
        while True:
            await anext(t)
            await bot.before_start(tg)
            try:
                async with ClientSession() as session:
                    url = f"{BASE_WS_URL}{gather_subscriptions(bot)}"
                    async with session.ws_connect(
                        url,
                        headers={
                            "room-id": room_id,
                            "api-token": api_key,
                            "user-agent": USER_AGENT,
                        },
                    ) as ws:
                        ka_task = tg.create_task(_send_keepalive(ws))
                        try:
                            session_metadata = await _receive_metadata(ws)
                            if isinstance(session_metadata, Error):
                                print(f"ERROR: {session_metadata}")
                                return

                            highrise = Highrise(
                                ws=ws,
                                tg=tg,
                                my_id=str(session_metadata.user_id),
                            )
                            bot.highrise = highrise
                            bot.webapi = WebAPI()

                            _spawn_task(tg, bot.on_start(session_metadata))
                            await _receive_loop(ws, highrise, bot, tg, session_metadata)
                        finally:
                            ka_task.cancel()

            except _DoNotReconnect:
                return
            except (
                TimeoutError,
                ConnectionResetError,
                WSServerHandshakeError,
                WebSocketError,
            ):
                print("ERROR: reconnecting...")
            except (RuntimeError, OSError) as exc:
                log.exception("Unexpected bot_runner error; reconnecting: %s", exc)

            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Control runner
# ---------------------------------------------------------------------------
async def control_runner(bot_cls: type[BaseBot], room_id: str, api_key: str) -> None:
    async with TaskGroup() as tg:
        instances_to_bots: dict[str, asyncio.Task] = {}
        while True:
            try:
                async with ClientSession() as session:
                    url = f"{BASE_WS_URL}/control/{room_id}"
                    async with session.ws_connect(
                        url,
                        headers={
                            "api-token": api_key,
                            "user-agent": USER_AGENT,
                        },
                    ) as ws:
                        ka_task = tg.create_task(_send_keepalive(ws))
                        try:
                            metadata = await _receive_control_metadata(ws)
                            if isinstance(metadata, Error):
                                print(f"ERROR: {metadata}")
                                return

                            for instance_id in metadata.instance_ids:
                                if instance_id in instances_to_bots:
                                    continue
                                print(f"Starting bot for instance {instance_id}")
                                bot_task = tg.create_task(
                                    bot_runner(
                                        bot_cls(),
                                        f"3d/{instance_id}",
                                        api_key,
                                    )
                                )
                                instances_to_bots[instance_id] = bot_task

                            while True:
                                frame = await ws.receive(READ_TIMEOUT)
                                if frame.type in CLOSE_TYPES:
                                    print(
                                        "Control connection with ID: "
                                        f"{metadata.connection_id} closed by server,"
                                        " reconnecting."
                                    )
                                    break
                                if frame.type == WSMsgType.ERROR:
                                    return
                                if frame.type not in (
                                    WSMsgType.TEXT,
                                    WSMsgType.BINARY,
                                ):
                                    continue

                                data = loads_json(frame.data)
                                if not isinstance(data, dict):
                                    continue

                                event_type = data.get("_type")
                                if event_type == "InstanceStartedEvent":
                                    instance_id = str(data.get("instance_id", ""))
                                    if (
                                        instance_id
                                        and instance_id not in instances_to_bots
                                    ):
                                        bot_task = tg.create_task(
                                            bot_runner(
                                                bot_cls(),
                                                f"3d/{instance_id}",
                                                api_key,
                                            )
                                        )
                                        instances_to_bots[instance_id] = bot_task
                                elif event_type == "InstanceStoppedEvent":
                                    instance_id = str(data.get("instance_id", ""))
                                    task = instances_to_bots.pop(instance_id, None)
                                    if task is not None:
                                        task.cancel()
                        finally:
                            ka_task.cancel()

            except (
                TimeoutError,
                ConnectionResetError,
                WSServerHandshakeError,
                WebSocketError,
            ):
                print("ERROR: control reconnecting...")
            except (RuntimeError, OSError) as exc:
                log.exception("Unexpected control_runner error; reconnecting: %s", exc)

            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Multi-bot launcher
# ---------------------------------------------------------------------------
def import_bot_class(bot_path: str) -> type[BaseBot]:
    if ":" not in bot_path:
        raise ValueError("BOT_PATH must be in format module:ClassName")
    module_name, class_name = bot_path.split(":", 1)
    module = importlib.import_module(module_name)
    bot_class = getattr(module, class_name)
    return bot_class


async def main_async(definitions: list[BotDefinition]) -> None:
    async with TaskGroup() as tg:
        for index, definition in enumerate(definitions):
            tg.create_task(
                bot_runner(
                    definition.bot,
                    definition.room_id,
                    definition.api_token,
                )
            )
            if index < len(definitions) - 1:
                print("Bot started. Waiting 1 second(s) before starting the next bot.")
                await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())

    parser = argparse.ArgumentParser(
        description="Run a Highrise bot using the standalone fast SDK."
    )
    parser.add_argument(
        "bot_definition",
        nargs=3,
        metavar=("BOT_PATH", "ROOM_ID", "API_TOKEN"),
        help="Example: HighriseRadio1:HighriseBot ROOM_ID TOKEN",
    )
    parser.add_argument(
        "--extra_bot",
        nargs=3,
        action="append",
        default=[],
        metavar=("BOT_PATH", "ROOM_ID", "API_TOKEN"),
        help="Optional additional bot definition.",
    )
    args = parser.parse_args()

    first_bot_path, first_room_id, first_token = args.bot_definition

    if first_room_id.startswith("3d/"):
        room_id = first_room_id[3:]
        bot_cls = import_bot_class(first_bot_path)
        return asyncio.run(control_runner(bot_cls, room_id, first_token))

    definitions: list[BotDefinition] = []
    all_defs = [tuple(args.bot_definition)]
    for extra in args.extra_bot:
        all_defs.append(tuple(extra))

    for bot_path, room_id, api_token in all_defs:
        bot_class = import_bot_class(str(bot_path))
        definitions.append(
            BotDefinition(
                bot=bot_class(),
                room_id=str(room_id),
                api_token=str(api_token),
            )
        )

    return asyncio.run(main_async(definitions))


if __name__ == "__main__":
    main()
