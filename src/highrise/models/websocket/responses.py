from dataclasses import dataclass, field
from typing import TypeVar, Generic, Any
from collections.abc import Coroutine, Callable

from ..base_response import BaseResponse
from .highrise_models import (
    MessageEntry,
    ConversationEntry,
    User,
    Position,
    AnchorPosition,
    OutfitItem,
    CurrencyItem,
    VoiceStatus,
    TipUserResult,
    WalletCurrency,
    ItemPurchaseResult
)

TPage = TypeVar("TPage", bound="BaseResponse")


@dataclass
class AcknowledgementResponse(BaseResponse):
    """A generic response for requests that only need to confirm
    success or failure, with no additional data returned.

    Used for actions like sending a chat message, whisper, or
    performing a moderation action, where the only thing that
    matters is whether the server accepted the request.

    Inherits `ok`, `error`, and `has_error()` directly from
    `BaseResponse` with no extra fields or overrides needed.
    """
    pass

class ResponseIterator(Generic[TPage]):
    """Handles the async iteration state safely. Works for any paginated BaseResponse subclass that exposes `next_page_fn`."""

    def __init__(self, initial_response: TPage):
        self._current_response: TPage | None = initial_response
        self._first_page_yielded = False

    async def __anext__(self) -> TPage:
        if not self._first_page_yielded:
            self._first_page_yielded = True
            return self._current_response

        if self._current_response is None or self._current_response.next_page_fn is None:
            raise StopAsyncIteration

        nxt = await self._current_response.next_page_fn()
        self._current_response = nxt
        return nxt

@dataclass
class GetMessagesResponse(BaseResponse):
    """Response for fetching messages from a single conversation.

    `next_page_fn`, when not None, is a zero-arg async callable
    that fetches the next page. Set externally by
    `HighriseApi.get_messages` after this response is built, since
    paging needs the conversation_id which isn't part of the raw
    payload. Supports `async for page in response:`.
    """
    messages: list[MessageEntry] = field(default_factory=list)
    next_page_fn: Callable[[], Coroutine[Any, Any, "GetMessagesResponse"]] | None = None

    def _build(self, data: Any) -> None:
        raw_messages = data.get("messages", [])
        self.messages = [MessageEntry(**m) for m in raw_messages]

    def __aiter__(self) -> "ResponseIterator[GetMessagesResponse]":
        return ResponseIterator(self)

@dataclass
class GetConversationsResponse(BaseResponse):
    """Response for fetching the bot's list of conversations.

    `not_joined` is the count of conversations the bot hasn't
    joined yet. `next_page_fn` works the same way as on
    `GetMessagesResponse`.
    """
    conversations: list[ConversationEntry] = field(default_factory=list)
    not_joined: int = 0
    next_page_fn: Callable[[], Coroutine[Any, Any, "GetConversationsResponse"]] | None = None

    def _build(self, data: Any) -> None:
        raw_conversations = data.get("conversations", [])
        self.conversations = [self._parse_conversation(c) for c in raw_conversations]
        self.not_joined = data.get("not_joined", 0)

    @staticmethod
    def _parse_conversation(raw: dict) -> ConversationEntry:
        raw_last_message = raw.get("last_message")
        last_message = MessageEntry(**raw_last_message) if raw_last_message else None

        return ConversationEntry(
            id=raw["id"],
            did_join=raw["did_join"],
            unread_count=raw["unread_count"],
            last_message=last_message,
            muted=raw["muted"],
            member_ids=raw.get("member_ids"),
            name=raw.get("name"),
            owner_id=raw.get("owner_id"),
        )

    def __aiter__(self) -> "ResponseIterator[GetConversationsResponse]":
        return ResponseIterator(self)

@dataclass
class TipUserResponse(BaseResponse):
    """Response for tipping a user."""
    result: TipUserResult | None = None

    def _build(self, data: Any) -> None:
        self.result = data.get("result")

@dataclass
class GetUserOutfitResponse(BaseResponse):
    """Response for fetching a user's outfit."""
    outfit: list[OutfitItem] = field(default_factory=list)
    count: int = 0

    def _build(self, data: Any) -> None:
        raw_outfit = data.get("outfit", [])
        self.outfit = [OutfitItem(**item) for item in raw_outfit]
        self.count = len(self.outfit)

    def has_item(self, item_id: str) -> bool:
        """Checks whether the outfit contains an item with the given id."""
        return any(item.id == item_id for item in self.outfit)

    def find_item(self, item_id: str) -> OutfitItem | None:
        """Finds the item with the given id in the outfit, or None if not present."""
        return next((item for item in self.outfit if item.id == item_id), None)

@dataclass
class GetRoomUsersResponse(BaseResponse):
    """The list of users in the room, alongside their positions."""
    content: list[tuple[User, Position | AnchorPosition]] = field(default_factory=list)

    def _build(self, data: Any) -> None:
        raw_content = data.get("content", [])
        parsed: list[tuple[User, Position | AnchorPosition]] = []

        for raw_user, raw_pos in raw_content:
            user = User(id=raw_user.get("id"), username=raw_user.get("username"))

            if "entity_id" in raw_pos:
                position: Position | AnchorPosition = AnchorPosition(
                    entity_id=raw_pos.get("entity_id"),
                    anchor_ix=raw_pos.get("anchor_ix"),
                )
            else:
                position = Position(
                    x=raw_pos.get("x", 0),
                    y=raw_pos.get("y", 0),
                    z=raw_pos.get("z", 0),
                    facing=raw_pos.get("facing", "FrontRight"),
                )

            parsed.append((user, position))

        self.content = parsed

    def users_count(self) -> int:
        """Returns the number of users currently in the room."""
        return len(self.content)

    def find_user(self, identifier: str) -> tuple[User, Position | AnchorPosition] | None:
        """Finds a (user, position) pair by user id or username."""
        return next(
            (pair for pair in self.content if pair[0].id == identifier or pair[0].username == identifier),
            None,
        )

    def has_user(self, identifier: str) -> bool:
        """Checks whether a user with the given id or username is in the room."""
        return self.find_user(identifier) is not None

    def get_username(self, user_id: str) -> str | None:
        """Returns the username for the given user id, or None if not found."""
        pair = self.find_user(user_id)
        return pair[0].username if pair else None

    def get_user_id(self, username: str) -> str | None:
        """Returns the user id for the given username, or None if not found."""
        pair = self.find_user(username)
        return pair[0].id if pair else None

    def get_position(self, identifier: str) -> Position | AnchorPosition | None:
        """Returns the position for the given user id or username, or None if not found."""
        pair = self.find_user(identifier)
        return pair[1] if pair else None

@dataclass
class CheckVoiceChatResponse(BaseResponse):
    """The status of voice chat in the room."""
    seconds_left: int = 0
    auto_speakers: set[str] = field(default_factory=set)
    users: dict[str, VoiceStatus] = field(default_factory=dict)

    def _build(self, data: Any) -> None:
        self.seconds_left = data.get("seconds_left", 0)
        self.auto_speakers = set(data.get("auto_speakers", []))
        self.users = data.get("users", {})

@dataclass
class GetRoomPrivilegeResponse(BaseResponse):
    """The room privileges for a user."""
    moderator: bool | None = None
    designer: bool | None = None

    def _build(self, data: Any) -> None:
        content = data.get("content", {})
        self.moderator = content.get("moderator")
        self.designer = content.get("designer")

@dataclass
class GetWalletResponse(BaseResponse):
    """The bot's wallet. Contains Highrise currencies."""
    content: list[CurrencyItem] = field(default_factory=list)

    def _build(self, data: Any) -> None:
        raw_content = data.get("content", [])
        self.content = [CurrencyItem(**item) for item in raw_content]

    def get(self, currency_type: WalletCurrency) -> int | None:
        """Returns the amount held for the given currency type, or `None` if not present."""
        return next((item.amount for item in self.content if item.type == currency_type), None)

@dataclass
class BuyItemResponse(BaseResponse):
    """Response for buying an item."""
    result: ItemPurchaseResult | None = None

    def _build(self, data: Any) -> None:
        self.result = data.get("result")

@dataclass
class GetInventoryResponse(BaseResponse):
    """The bot's inventory."""
    items: list[OutfitItem] = field(default_factory=list)

    def _build(self, data: Any) -> None:
        raw_items = data.get("items", [])
        self.items = [OutfitItem(**item) for item in raw_items]

    def has_item(self, item_id: str) -> bool:
        """Checks whether the inventory contains an item with the given id."""
        return any(item.id == item_id for item in self.items)

    def find_item(self, item_id: str) -> OutfitItem | None:
        """Finds the item with the given id in the inventory, or None if not present."""
        return next((item for item in self.items if item.id == item_id), None)