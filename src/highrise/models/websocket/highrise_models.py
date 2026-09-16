from dataclasses import dataclass, field
from typing import Literal
import math

Facing = Literal["FrontRight", "FrontLeft", "BackRight", "BackLeft"]
ModerationType = Literal["kick", "mute", "ban", "unban", "unmute"]
Reaction = Literal["clap", "heart", "thumbs", "wave", "wink"]
MessageType = Literal["text", "invite"]
CurrencyType = Literal['gold', 'bubble']
WalletCurrency = Literal["gold", "room_boost_tokens", "room_voice_tokens"]
ItemPurchaseResult = Literal["success", "insufficient_funds"]
TipUserResult = Literal["success", "insufficient_funds"]
VoiceStatus = Literal["invited", "voice", "muted"]
TipType = Literal[
    "gold_bar_1",
    "gold_bar_5",
    "gold_bar_10",
    "gold_bar_50",
    "gold_bar_100",
    "gold_bar_500",
    "gold_bar_1k",
    "gold_bar_5000",
    "gold_bar_10k",
]
TIP_VALUES: dict[int, TipType] = {
    1: "gold_bar_1",
    5: "gold_bar_5",
    10: "gold_bar_10",
    50: "gold_bar_50",
    100: "gold_bar_100",
    500: "gold_bar_500",
    1000: "gold_bar_1k",
    5000: "gold_bar_5000",
    10000: "gold_bar_10k",
}

# These classes are constructed for every single incoming WebSocket event
# (chat, join/leave, movement, tips, emotes...), so they're `slots=True`:
# no per-instance __dict__, lower memory per object, faster attribute access.
@dataclass(slots=True)
class User:
    """A user in the room."""
    id: str
    username: str

@dataclass(slots=True)
class Sender(User):
    """The user who sent a tip."""

@dataclass(slots=True)
class Receiver(User):
    """The user who received a tip."""

@dataclass(slots=True)
class Position:
    """A player's position in the room."""
    x: float
    y: float
    z: float
    facing: Facing = "FrontRight"

    def distance_to(self, other: "Position") -> float:
        """Calculate the 3D distance to another position."""
        return math.hypot(self.x - other.x, self.y - other.y, self.z - other.z)

    def offset(self, dx: int = 0, dy: int = 0, dz: int = 0) -> "Position":
        """Return a new Position shifted by the given values, keeping the facing direction."""
        return Position(
            x=self.x + dx,
            y=self.y + dy,
            z=self.z + dz,
            facing=self.facing
        )

    def as_tuple(self) -> tuple[float, float, float]:
        """Return the coordinates as a simple (x, y, z) tuple, ignoring facing direction."""
        return (self.x, self.y, self.z)

@dataclass(slots=True)
class AnchorPosition:
    """Position when a user is anchored to an object (sitting, etc.)."""
    entity_id: str
    anchor_ix: int

@dataclass(slots=True)
class Message:
    """A chat, whisper, or direct message."""

    content: str
    """The full text content of the message."""

    _args: list[str] | None = field(default=None, init=False, repr=False)
    _rest: list[str] | None = field(default=None, init=False, repr=False)
    _mentions: list[str] | None = field(default=None, init=False, repr=False)

    def _get_args(self) -> list[str]:
        args = self._args
        if args is None:
            args = self.content.strip().split() if self.content else []
            self._args = args
        return args

    def command(self) -> str | None:
        """Returns the first word of the message, treated as the
        command name if this message is a command."""
        args = self._get_args()
        return args[0] if args else None

    def args(self, index: int | None = None) -> list[str] | str | None:
        """Returns the message arguments (excluding the command itself).
        Pass an index to get a specific argument, or omit it to get
        the full list."""
        all_args = self._get_args()
        if not all_args or len(all_args) <= 1:
            return [] if index is None else None

        if index is None:
            if self._rest is None:
                self._rest = all_args[1:]
            return self._rest

        if index >= 0:
            idx = index + 1
            return all_args[idx] if idx < len(all_args) else None
        else:
            return all_args[index] if abs(index) <= len(all_args) - 1 else None

    def mentions(self, index: int | None = None) -> list[str] | str | None:
        """Returns all mentioned usernames (words starting with '@',
        with the '@' stripped). Pass an index to get a specific
        mention, or omit it to get the full list."""
        if self._mentions is None:
            self._mentions = [
                word[1:] for word in self._get_args() if word.startswith("@")
            ]

        if index is None:
            return self._mentions

        if index >= 0:
            return self._mentions[index] if index < len(self._mentions) else None
        else:
            return self._mentions[index] if abs(index) <= len(self._mentions) else None


@dataclass(slots=True)
class Conversation:
    """A direct message conversation."""
    id: str
    is_new_conversation: bool

@dataclass(slots=True)
class Item:
    """A currency amount exchanged in a tip."""
    type: CurrencyType
    amount: int

@dataclass(slots=True)
class ModerationAction:
    """The type of moderation action taken."""
    type: ModerationType
    duration: int | None = None


@dataclass(slots=True)
class RoomInfo:
    """Room information included in the session metadata."""
    owner_id: str
    room_name: str

    @classmethod
    def _from_raw(cls, data: dict) -> "RoomInfo":
        room_info = data.get("room_info") or {}
        return cls(
            owner_id=room_info.get("owner_id", ""),
            room_name=room_info.get("room_name", ""),
        )

@dataclass(slots=True)
class SessionMetadata:
    """Initial session data.

    Sent once, as the first message when a connection is established.

    - user_id: the bot's user id.
    - room_info: additional information about the connected room.
    - rate_limits: a dict of rate limits, keyed by rate limit name, each value a (limit, period) tuple.
    - connection_id: the connection id of the websocket used in this bot connection.
    - sdk_version: the SDK version recommended by the server, if the client identified itself as an SDK.
    """
    user_id: str
    room_info: RoomInfo
    rate_limits: dict[str, tuple[int, float]]
    connection_id: str
    sdk_version: str | None = None

    @classmethod
    def _from_raw(cls, data: dict) -> "SessionMetadata":
        raw_rate_limits = data.get("rate_limits") or {}
        rate_limits = {
            key: tuple(value) for key, value in raw_rate_limits.items()
        }

        return cls(
            user_id=data.get("user_id", ""),
            room_info=RoomInfo._from_raw(data),
            rate_limits=rate_limits,
            connection_id=data.get("connection_id", ""),
            sdk_version=data.get("sdk_version"),
        )

@dataclass(slots=True)
class MessageEntry:
    """A single message entry, as returned by `get_messages` or nested
    inside a `Conversation` as its `last_message`."""
    message_id: str
    conversation_id: str
    createdAt: str
    content: str
    sender_id: str
    category: str

@dataclass(slots=True)
class ConversationEntry:
    """A single conversation entry as returned by `get_conversations`."""
    id: str
    did_join: bool
    unread_count: int
    last_message: MessageEntry | None
    muted: bool
    member_ids: list[str] | None = None
    name: str | None = None
    owner_id: str | None = None

@dataclass(slots=True)
class OutfitItem:
    """A single item in a user's outfit."""
    type: str
    amount: int
    id: str
    account_bound: bool
    active_palette: int

@dataclass(slots=True)
class RoomPermissions:
    """Room privilege flags to assign to a user."""
    moderator: bool | None = None
    designer: bool | None = None

@dataclass(slots=True)
class CurrencyItem:
    """A Highrise currency amount. Common types: `gold`, `bubbles`."""
    type: CurrencyType
    amount: int

@dataclass(slots=True)
class Credentials:
    """Room/token pair used for the current session."""
    room_id: str
    api_token: str