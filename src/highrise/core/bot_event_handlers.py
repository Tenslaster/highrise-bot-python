from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..base_bot import BaseBot

from ..models.websocket.highrise_models import *


def _get_user(bot: "BaseBot", data: dict | None) -> User:
    data = data or {}
    uid = data.get("id")
    if uid:
        cached = bot.cached_users.find_user(uid)
        if cached is not None:
            return cached[0]
    return User(str(uid or ""), str(data.get("username", "")))


def _parse_position(data: dict) -> Position:
    return Position(data.get("x", 0.0), data.get("y", 0.0), data.get("z", 0.0), data.get("facing", "FrontRight"))


async def handle_session_metadata(bot: "BaseBot", data: dict[str, Any]) -> None:
    metadata = SessionMetadata._from_raw(data)
    bot._context.session_metadata = metadata
    await bot.on_start(metadata)
    if bot._connection._session_generation > 1:
        await bot.on_reconnect(metadata)
    bot.logger.info("Successfully connected to Highrise!")


async def handle_chat_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    user_data = data.get("user") or {}
    user = _get_user(bot, user_data)
    message = Message(str(data.get("message") or ""))
    if user_data.get("whisper", False):
        await bot.on_whisper(user, message)
    else:
        await bot.on_chat(user, message)


async def handle_user_join(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    position_data = data.get("position") or {}
    position = AnchorPosition(position_data["entity_id"], position_data.get("anchor_ix")) if "entity_id" in position_data else _parse_position(position_data)
    bot.cached_users._add(user, position)
    await bot.on_user_join(user, position)


async def handle_user_leave(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    bot.cached_users._remove(user.id)
    await bot.on_user_leave(user)


async def handle_user_moved(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    position_data = data.get("position") or {}
    position = None
    anchor = None
    if "entity_id" in position_data:
        anchor = AnchorPosition(position_data.get("entity_id"), position_data.get("anchor_ix"))
        bot.cached_users._update(user.id, anchor)
    elif position_data:
        position = _parse_position(position_data)
        bot.cached_users._update(user.id, position)
    await bot.on_user_move(user, position, anchor)


async def handle_tip_reaction(bot: "BaseBot", data: dict[str, Any]) -> None:
    sender = _get_user(bot, data.get("sender"))
    receiver = _get_user(bot, data.get("receiver"))
    raw = data.get("item") or {}
    tip = Item(raw.get("type"), raw.get("amount"))
    await bot.on_tip(sender, receiver, tip)


async def handle_reaction_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    receiver = _get_user(bot, data.get("receiver"))
    await bot.on_reaction(user, data.get("reaction", ""), receiver)


async def handle_emote_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    user = _get_user(bot, data.get("user"))
    receiver_data = data.get("receiver")
    receiver = _get_user(bot, receiver_data) if receiver_data else None
    await bot.on_emote(user, str(data.get("emote_id") or ""), receiver)


async def handle_message_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    conversation_id = str(data.get("conversation_id") or "")
    conversation = Conversation(conversation_id, bool(data.get("is_new_conversation", False)))
    message = None
    if bot.config.auto_fetch.direct_message:
        response = await bot.highrise.get_messages(conversation_id)
        if response.ok and response.messages:
            message = Message(response.messages[0].content)
    await bot.on_message(str(data.get("user_id") or ""), message, conversation)


async def handle_room_moderate(bot: "BaseBot", data: dict[str, Any]) -> None:
    moderation_type = str(data.get("moderationType") or "unknown")
    duration = data.get("duration")
    if moderation_type == "mute" and duration == 1:
        moderation_type = "unmute"
    await bot.on_moderate(str(data.get("moderatorId") or ""), str(data.get("targetUserId") or ""), ModerationAction(moderation_type, duration))


async def handle_channel_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    await bot.on_channel(str(data.get("sender_id") or ""), str(data.get("message") or ""), list(data.get("tags") or []))


async def handle_voice_event(bot: "BaseBot", data: dict[str, Any]) -> None:
    users = data.get("users") or []
    await bot.on_voice_change(users, int(data.get("seconds_left") or 0))


EVENT_HANDLERS = {
    "SessionMetadata": handle_session_metadata,
    "ChatEvent": handle_chat_event,
    "UserJoinedEvent": handle_user_join,
    "UserLeftEvent": handle_user_leave,
    "UserMovedEvent": handle_user_moved,
    "TipReactionEvent": handle_tip_reaction,
    "ReactionEvent": handle_reaction_event,
    "EmoteEvent": handle_emote_event,
    "MessageEvent": handle_message_event,
    "RoomModeratedEvent": handle_room_moderate,
    "ChannelEvent": handle_channel_event,
    "VoiceEvent": handle_voice_event,
}
