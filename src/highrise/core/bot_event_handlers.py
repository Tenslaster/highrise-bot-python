from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..base_bot import BaseBot

from ..models.websocket.highrise_models import *


def _parse_user(data: dict | None) -> User:
    data = data or {}
    return User(str(data.get("id", "")), str(data.get("username", "")))


def _get_user(bot: "BaseBot", data: dict | None) -> User:
    """Returns an existing cached User instance if present to avoid GC churn;
    otherwise creates and returns a new User instance."""
    if not data:
        return User("", "")
    uid = data.get("id")
    if uid:
        cached = bot.cached_users.find_user(uid)
        if cached is not None:
            return cached[0]
        return User(str(uid), str(data.get("username", "")))
    return User("", str(data.get("username", "")))


def _parse_position(pos_data: dict) -> Position:
    return Position(
        pos_data.get("x", 0.0),
        pos_data.get("y", 0.0),
        pos_data.get("z", 0.0),
        pos_data.get("facing"),
    )


async def handle_session_metadata(bot: "BaseBot", data: dict[str, Any]) -> None:
    metadata = SessionMetadata._from_raw(data)
    bot._context.session_metadata = metadata
    await bot.on_start(metadata)
    if bot._connection._session_generation > 1:
        try:
            await bot.on_reconnect(metadata)
        except Exception as exc:
            bot.logger.error("Error in on_reconnect hook: %s", exc, exc_info=True)
    bot.logger.info("Successfully connected to Highrise!")


async def handle_chat_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    user_data = data.get("user") or {}
    is_whisper = bool(user_data.get("whisper", False))
    user = _get_user(bot, user_data)
    message = Message(str(data.get("message") or ""))

    if is_whisper:
        bot.awaiter._feed("on_whisper", (user, message))
        await bot.on_whisper(user, message)
    else:
        bot.awaiter._feed("on_chat", (user, message))
        await bot.on_chat(user, message)


async def handle_user_join(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _parse_user(data.get("user"))
    position = _parse_position(data.get("position") or {})
    bot.cached_users._add(user, position)
    await bot.on_user_join(user, position)


async def handle_user_leave(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    bot.cached_users._remove(user.id)
    await bot.on_user_leave(user)


async def handle_user_moved(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    pos_data = data.get("position") or {}
    position = None
    anchor = None

    if pos_data:
        if "entity_id" in pos_data:
            anchor = AnchorPosition(pos_data.get("entity_id"), pos_data.get("anchor_ix"))
            bot.cached_users._update(user.id, anchor)
        else:
            position = _parse_position(pos_data)
            bot.cached_users._update(user.id, position)

    await bot.on_user_move(user, position, anchor)


async def handle_tip_reaction(bot: "BaseBot", data: dict[str, Any]) -> None:
    sender = _get_user(bot, data.get("sender"))
    receiver = _get_user(bot, data.get("receiver"))
    item_data = data.get("item") or {}
    item = Item(item_data.get("type"), item_data.get("amount"))
    bot.awaiter._feed("on_tip", (sender, receiver, item))
    await bot.on_tip(sender, receiver, item)


async def handle_emote_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    emote_id = str(data.get("emote_id") or "")
    receiver_data = data.get("receiver")
    receiver = _get_user(bot, receiver_data) if receiver_data else None
    bot.awaiter._feed("on_emote", (user, emote_id, receiver))
    await bot.on_emote(user, emote_id, receiver)


async def handle_message_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    conversation_id = str(data.get("conversation_id") or "")
    conversation = Conversation(
        id=conversation_id,
        is_new_conversation=bool(data.get("is_new_conversation", False)),
    )
    user_id = str(data.get("user_id") or "")

    message = None
    if bot.config.auto_fetch.direct_message:
        response = await bot.highrise.get_messages(conversation_id)
        if response.ok and response.messages:
            message = Message(response.messages[0].content)

    bot.awaiter._feed("on_message", (user_id, message, conversation))
    await bot.on_message(user_id, message, conversation)


async def handle_room_moderate(bot: "BaseBot", data: dict[str, Any]) -> None:
    moderator_id = str(data.get("moderatorId") or "")
    target_id = str(data.get("targetUserId") or "")
    moderation_type = str(data.get("moderationType") or "unknown")
    duration = data.get("duration")
    if moderation_type == "mute" and duration == 1:
        moderation_type = "unmute"
    action = ModerationAction(type=moderation_type, duration=duration)
    await bot.on_moderate(moderator_id, target_id, action)


async def handle_channel_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    message = str(data.get("message") or "")
    await bot.on_channel(
        str(data.get("sender_id") or ""),
        message,
        data.get("tags", []),
    )


EVENT_HANDLERS = {
    "SessionMetadata": handle_session_metadata,
    "ChatEvent": handle_chat_event,
    "UserJoinedEvent": handle_user_join,
    "UserLeftEvent": handle_user_leave,
    "UserMovedEvent": handle_user_moved,
    "TipReactionEvent": handle_tip_reaction,
    "EmoteEvent": handle_emote_event,
    "MessageEvent": handle_message_event,
    "RoomModeratedEvent": handle_room_moderate,
    "ChannelEvent": handle_channel_event,
}
