"""
highrise_fast/validation.py
Official-compatible native validator with Semantic Bounds and Reason Codes.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "BASE_PAYLOADS",
    "HighriseFastValidationError",
    "ReasonCode",
    "ValidationErrorDetail",
    "validate_server_message",
]

# Valid Literal values from the official SDK
FACING_VALUES = {"FrontRight", "FrontLeft", "BackRight", "BackLeft"}
MODERATION_VALUES = {"kick", "mute", "unmute", "ban", "unban"}
REACTION_VALUES = {"clap", "heart", "thumbs", "wave", "wink"}
VOICE_STATUS_VALUES = {"voice", "muted"}


class ReasonCode:
    MISSING_FIELD = "MISSING_FIELD"
    WRONG_TYPE = "WRONG_TYPE"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"
    INVALID_LENGTH = "INVALID_LENGTH"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class ValidationErrorDetail:
    def __init__(
        self,
        path: str,
        message: str,
        expected: str = "",
        got: str = "",
        value: Any = None,
        reason_code: str = ReasonCode.UNKNOWN_ERROR,
    ):
        self.path = path
        self.message = message
        self.expected = expected
        self.got = got
        self.value = value
        self.reason_code = reason_code

    def render(self) -> str:
        return f"[{self.reason_code}] {self.path}: {self.message} (expected {self.expected}, got {self.got})"


class HighriseFastValidationError(ValueError):
    def __init__(self, errors: list[ValidationErrorDetail] | str):
        if isinstance(errors, str):
            self.errors = [ValidationErrorDetail("$", errors)]
        else:
            self.errors = errors
        super().__init__(self.render())

    def render(self) -> str:
        return "highrise_fast strict validation failed:\n" + "\n".join(
            f"  - {e.render()}" for e in self.errors
        )

    def __str__(self) -> str:
        return self.render()


def _type_name(value: Any) -> str:
    return type(value).__name__


def _is_empty_iterable(value: Any) -> bool:
    return isinstance(value, (str, dict)) and len(value) == 0


# ─────────────────────────────────────────────────────────────
# SCALAR COERCION & VALIDATION
# ─────────────────────────────────────────────────────────────
def _require_str(data: dict, key: str, path: str) -> str:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required string",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    return str(data[key])


def _require_int(data: dict, key: str, path: str) -> int:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required int",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    value = data[key]
    if value is None or isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be int-compatible",
                    expected="int",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be int-compatible",
                    expected="int",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )


def _require_float(data: dict, key: str, path: str) -> float:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required float",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    value = data[key]
    if value is None or isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be float-compatible",
                    expected="float",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be float-compatible",
                    expected="float",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )


def _require_bool(data: dict, key: str, path: str) -> bool:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required bool",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    return bool(data[key])


def _require_literal(data: dict, key: str, path: str, allowed: set[str]) -> str:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required literal",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    value = data[key]
    if not isinstance(value, str) or value not in allowed:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    f"must be one of {sorted(allowed)}",
                    expected="literal",
                    got=repr(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    return value


def _require_optional_literal(
    data: dict, key: str, path: str, allowed: set[str]
) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, str) or value not in allowed:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    f"must be one of {sorted(allowed)}",
                    expected="literal",
                    got=repr(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    return value


# ─────────────────────────────────────────────────────────────
# DICT FIELDS
# ─────────────────────────────────────────────────────────────
def _require_dict(data: dict, key: str, path: str) -> dict:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required dict",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    value = data[key]
    if not isinstance(value, dict):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be dict",
                    expected="dict",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    return value


def _require_optional_dict(data: dict, key: str, path: str) -> dict | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, dict):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be dict or null",
                    expected="dict",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    return value


def _require_optional_str(data: dict, key: str, path: str) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    return str(value)


def _require_optional_int(data: dict, key: str, path: str) -> int | None:
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be int-compatible or null",
                    expected="int",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be int-compatible or null",
                    expected="int",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )


def _require_nullable_int(data: dict, key: str, path: str) -> int | None:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required nullable int",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    value = data[key]
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be int-compatible or null",
                    expected="int",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be int-compatible or null",
                    expected="int",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )


def _require_default_bool(data: dict, key: str, path: str) -> bool:
    if key not in data:
        return False
    return bool(data[key])


def _require_default_optional_str(data: dict, key: str, path: str) -> str | None:
    return _require_optional_str(data, key, path)


# ─────────────────────────────────────────────────────────────
# LIST FIELDS
# ─────────────────────────────────────────────────────────────
def _check_list(data: dict, key: str, path: str) -> list:
    if key not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "Missing required list",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ]
        )
    value = data[key]
    if _is_empty_iterable(value):
        return []
    if not isinstance(value, list):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    f"{path}.{key}",
                    "must be list",
                    expected="list",
                    got=_type_name(value),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    return value


def _check_list_dicts(data: dict, key: str, path: str) -> list:
    value = _check_list(data, key, path)
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise HighriseFastValidationError(
                [
                    ValidationErrorDetail(
                        f"{path}.{key}[{i}]",
                        "must be dict",
                        expected="dict",
                        got=_type_name(item),
                        reason_code=ReasonCode.WRONG_TYPE,
                    )
                ]
            )
    return value


def _check_list_tuples(data: dict, key: str, path: str, expected_len: int) -> list:
    value = _check_list(data, key, path)
    for i, row in enumerate(value):
        row_path = f"{path}.{key}[{i}]"
        if not isinstance(row, (list, tuple)):
            raise HighriseFastValidationError(
                [
                    ValidationErrorDetail(
                        row_path,
                        "must be list/tuple",
                        expected="list",
                        got=_type_name(row),
                        reason_code=ReasonCode.WRONG_TYPE,
                    )
                ]
            )
        if len(row) != expected_len:
            raise HighriseFastValidationError(
                [
                    ValidationErrorDetail(
                        row_path,
                        f"length {len(row)} != {expected_len}",
                        expected=str(expected_len),
                        got=str(len(row)),
                        reason_code=ReasonCode.WRONG_TYPE,
                    )
                ]
            )
        if not isinstance(row[0], dict):
            raise HighriseFastValidationError(
                [
                    ValidationErrorDetail(
                        f"{row_path}[0]",
                        "must be dict",
                        expected="dict",
                        got=_type_name(row[0]),
                        reason_code=ReasonCode.WRONG_TYPE,
                    )
                ]
            )
    return value


# ─────────────────────────────────────────────────────────────
# ENTITY VALIDATORS
# ─────────────────────────────────────────────────────────────
def _validate_user(data: dict, path: str) -> None:
    _require_str(data, "id", path)
    _require_str(data, "username", path)


def _validate_position(data: dict, path: str) -> None:
    _require_float(data, "x", path)
    _require_float(data, "y", path)
    _require_float(data, "z", path)
    _require_optional_literal(data, "facing", path, FACING_VALUES)


def _validate_currency_item(data: dict, path: str) -> None:
    _require_str(data, "type", path)
    _require_int(data, "amount", path)


# ─────────────────────────────────────────────────────────────
# MESSAGE VALIDATORS
# ─────────────────────────────────────────────────────────────
def _validate_chat_event(payload: dict) -> None:
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")
    _require_str(payload, "message", "$")
    _require_bool(payload, "whisper", "$")


def _validate_user_joined(payload: dict) -> None:
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")
    position = _require_dict(payload, "position", "$")
    _validate_position(position, "$.position")


def _validate_user_left(payload: dict) -> None:
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")


def _validate_user_moved(payload: dict) -> None:
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")
    position = _require_dict(payload, "position", "$")
    _validate_position(position, "$.position")


def _validate_emote(payload: dict) -> None:
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")
    _require_str(payload, "emote_id", "$")
    receiver = _require_optional_dict(payload, "receiver", "$")
    if receiver is not None:
        _validate_user(receiver, "$.receiver")


def _validate_reaction(payload: dict) -> None:
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")
    _require_literal(payload, "reaction", "$", REACTION_VALUES)
    receiver = _require_dict(payload, "receiver", "$")
    _validate_user(receiver, "$.receiver")


def _validate_tip(payload: dict) -> None:
    sender = _require_dict(payload, "sender", "$")
    _validate_user(sender, "$.sender")
    receiver = _require_dict(payload, "receiver", "$")
    _validate_user(receiver, "$.receiver")
    item = _require_dict(payload, "item", "$")
    _validate_currency_item(item, "$.item")


def _validate_voice(payload: dict) -> None:
    users = _check_list_tuples(payload, "users", "$", 2)
    for i, row in enumerate(users):
        _validate_user(row[0], f"$.users[{i}][0]")
        status = row[1]
        if not isinstance(status, str) or status not in VOICE_STATUS_VALUES:
            raise HighriseFastValidationError(
                [
                    ValidationErrorDetail(
                        f"$.users[{i}][1]",
                        f"must be one of {sorted(VOICE_STATUS_VALUES)}",
                        expected="literal",
                        got=repr(status),
                        reason_code=ReasonCode.WRONG_TYPE,
                    )
                ]
            )
    _require_int(payload, "seconds_left", "$")


def _validate_channel(payload: dict) -> None:
    _require_str(payload, "sender_id", "$")
    _require_str(payload, "msg", "$")


def _validate_moderated(payload: dict) -> None:
    _require_str(payload, "moderatorId", "$")
    _require_str(payload, "targetUserId", "$")
    _require_literal(payload, "moderationType", "$", MODERATION_VALUES)
    _require_nullable_int(payload, "duration", "$")


def _validate_error(payload: dict) -> None:
    _require_str(payload, "message", "$")
    _require_default_bool(payload, "do_not_reconnect", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_message_event(payload: dict) -> None:
    _require_str(payload, "user_id", "$")
    _require_str(payload, "conversation_id", "$")
    _require_default_bool(payload, "is_new_conversation", "$")


def _validate_wallet(payload: dict) -> None:
    content = _check_list_dicts(payload, "content", "$")
    for i, item in enumerate(content):
        _validate_currency_item(item, f"$.content[{i}]")
    _require_str(payload, "rid", "$")


def _validate_room_users(payload: dict) -> None:
    content = _check_list_tuples(payload, "content", "$", 2)
    if len(content) < 2:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$.content",
                    "must contain at least 2 entries",
                    reason_code=ReasonCode.INVALID_LENGTH,
                )
            ]
        )
    for i, row in enumerate(content):
        _validate_user(row[0], f"$.content[{i}][0]")
        position = row[1]
        if not isinstance(position, dict):
            raise HighriseFastValidationError(
                [
                    ValidationErrorDetail(
                        f"$.content[{i}][1]",
                        "must be dict",
                        expected="dict",
                        got=_type_name(position),
                        reason_code=ReasonCode.WRONG_TYPE,
                    )
                ]
            )
        _validate_position(position, f"$.content[{i}][1]")


# ─────────────────────────────────────────────────────────────
# RESPONSE & ACK VALIDATORS
# ─────────────────────────────────────────────────────────────
def _validate_ack(payload: dict) -> None:
    _require_default_optional_str(payload, "rid", "$")


def _validate_backpack(payload: dict) -> None:
    _require_dict(payload, "backpack", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_room_privilege(payload: dict) -> None:
    _require_dict(payload, "content", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_voice_status(payload: dict) -> None:
    _require_int(payload, "seconds_left", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_outfit(payload: dict) -> None:
    _check_list(payload, "outfit", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_conversations(payload: dict) -> None:
    _check_list(payload, "conversations", "$")
    _require_int(payload, "not_joined", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_messages(payload: dict) -> None:
    _check_list(payload, "messages", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_result_ack(payload: dict) -> None:
    _require_str(payload, "result", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_inventory(payload: dict) -> None:
    _check_list(payload, "items", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_media(payload: dict) -> None:
    _require_default_optional_str(payload, "rid", "$")


# ─────────────────────────────────────────────────────────────
# SEMANTIC LAYER (Bounds Checking)
# ─────────────────────────────────────────────────────────────
def _validate_semantic_position(data: dict, path: str):
    for coord in ("x", "y", "z"):
        val = data.get(coord)
        if val is not None:
            try:
                fval = float(val)
                if not (-2000.0 <= fval <= 2000.0):
                    raise HighriseFastValidationError(
                        [
                            ValidationErrorDetail(
                                f"{path}.{coord}",
                                "out of map bounds",
                                reason_code=ReasonCode.OUT_OF_BOUNDS,
                            )
                        ]
                    )
            except (ValueError, TypeError):
                pass


def _validate_semantic_chat(payload: dict):
    msg = payload.get("message", "")
    if len(str(msg)) > 1024:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$.message",
                    "exceeds 1024 chars",
                    reason_code=ReasonCode.INVALID_LENGTH,
                )
            ]
        )


def _validate_semantic_wallet(payload: dict):
    content = payload.get("content", [])
    if isinstance(content, list):
        for i, item in enumerate(content):
            if isinstance(item, dict):
                amt = item.get("amount", 0)
                try:
                    if int(amt) < 0:
                        raise HighriseFastValidationError(
                            [
                                ValidationErrorDetail(
                                    f"$.content[{i}].amount",
                                    "negative wallet amount",
                                    reason_code=ReasonCode.OUT_OF_BOUNDS,
                                )
                            ]
                        )
                except (ValueError, TypeError):
                    pass


# ─────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────
_DISPATCH = {
    # Events
    "ChatEvent": _validate_chat_event,
    "UserJoinedEvent": _validate_user_joined,
    "UserLeftEvent": _validate_user_left,
    "UserMovedEvent": _validate_user_moved,
    "EmoteEvent": _validate_emote,
    "ReactionEvent": _validate_reaction,
    "TipReactionEvent": _validate_tip,
    "VoiceEvent": _validate_voice,
    "ChannelEvent": _validate_channel,
    "RoomModeratedEvent": _validate_moderated,
    "MessageEvent": _validate_message_event,
    "Error": _validate_error,
    # Responses
    "GetWalletResponse": _validate_wallet,
    "GetRoomUsersResponse": _validate_room_users,
    "GetBackpackResponse": _validate_backpack,
    "ChangeBackpackResponse": _validate_ack,
    "GetRoomPrivilegeResponse": _validate_room_privilege,
    "CheckVoiceChatResponse": _validate_voice_status,
    "GetUserOutfitResponse": _validate_outfit,
    "GetConversationsResponse": _validate_conversations,
    "SendMessageResponse": _validate_ack,
    "SendBulkMessageResponse": _validate_ack,
    "GetMessagesResponse": _validate_messages,
    "LeaveConversationResponse": _validate_ack,
    "BuyVoiceTimeResponse": _validate_result_ack,
    "BuyRoomBoostResponse": _validate_result_ack,
    "TipUserResponse": _validate_result_ack,
    "GetInventoryResponse": _validate_inventory,
    "SetOutfitResponse": _validate_ack,
    "BuyItemResponse": _validate_result_ack,
    "MessageMediaResponse": _validate_media,
    # Acks
    "ChatResponse": _validate_ack,
    "EmoteResponse": _validate_ack,
    "ReactionResponse": _validate_ack,
    "IndicatorResponse": _validate_ack,
    "ChannelResponse": _validate_ack,
    "KeepaliveResponse": _validate_ack,
    "TeleportResponse": _validate_ack,
    "FloorHitResponse": _validate_ack,
    "AnchorHitResponse": _validate_ack,
    "ModerateRoomResponse": _validate_ack,
    "ChangeRoomPrivilegeResponse": _validate_ack,
    "MoveUserToRoomResponse": _validate_ack,
    "InviteSpeakerResponse": _validate_ack,
    "RemoveSpeakerResponse": _validate_ack,
}


def validate_server_message(
    data: Any, strict: bool = False, strict_semantic: bool = False, **kwargs: Any
) -> dict:
    """
    Validate one incoming Highrise server message payload.
    """
    if not isinstance(data, dict):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$",
                    "payload must be an object",
                    expected="dict",
                    got=_type_name(data),
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ]
        )
    if "_type" not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$._type", "Missing _type", reason_code=ReasonCode.MISSING_FIELD
                )
            ]
        )

    message_type = data["_type"]
    handler = _DISPATCH.get(message_type)

    if handler is None:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$._type",
                    f"unknown _type {message_type!r}",
                    reason_code=ReasonCode.UNKNOWN_TYPE,
                )
            ]
        )

    handler(data)

    if strict_semantic:
        if message_type == "ChatEvent":
            _validate_semantic_chat(data)
        elif message_type in ("UserMovedEvent", "UserJoinedEvent"):
            pos = data.get("position")
            if isinstance(pos, dict):
                _validate_semantic_position(pos, "$.position")
        elif message_type == "GetWalletResponse":
            _validate_semantic_wallet(data)

    return data


# ─────────────────────────────────────────────────────────────
# BASE PAYLOADS (Fixtures for Benchmark / Fuzzer)
# ─────────────────────────────────────────────────────────────
BASE_PAYLOADS = {
    "ChatEvent": {
        "_type": "ChatEvent",
        "user": {"id": "u1", "username": "test"},
        "message": "hello",
        "whisper": False,
    },
    "EmoteEvent": {
        "_type": "EmoteEvent",
        "user": {"id": "u1", "username": "test"},
        "emote_id": "e1",
    },
    "ReactionEvent": {
        "_type": "ReactionEvent",
        "user": {"id": "u1", "username": "test"},
        "reaction": "heart",
        "receiver": {"id": "u2", "username": "test2"},
    },
    "UserJoinedEvent": {
        "_type": "UserJoinedEvent",
        "user": {"id": "u1", "username": "test"},
        "position": {"x": 1.0, "y": 2.0, "z": 3.0, "facing": "FrontRight"},
    },
    "UserLeftEvent": {
        "_type": "UserLeftEvent",
        "user": {"id": "u1", "username": "test"},
    },
    "ChannelEvent": {
        "_type": "ChannelEvent",
        "sender_id": "u1",
        "msg": "hello",
        "tags": [],
    },
    "TipReactionEvent": {
        "_type": "TipReactionEvent",
        "sender": {"id": "u1", "username": "test"},
        "receiver": {"id": "u2", "username": "test2"},
        "item": {"type": "gold", "amount": 1},
    },
    "UserMovedEvent": {
        "_type": "UserMovedEvent",
        "user": {"id": "u1", "username": "test"},
        "position": {"x": 1.0, "y": 2.0, "z": 3.0, "facing": "FrontRight"},
    },
    "VoiceEvent": {
        "_type": "VoiceEvent",
        "users": [[{"id": "u1", "username": "test"}, "voice"]],
        "seconds_left": 10,
    },
    "MessageEvent": {
        "_type": "MessageEvent",
        "user_id": "u1",
        "conversation_id": "c1",
        "is_new_conversation": False,
    },
    "RoomModeratedEvent": {
        "_type": "RoomModeratedEvent",
        "moderatorId": "u1",
        "targetUserId": "u2",
        "moderationType": "mute",
        "duration": 60,
    },
    "Error": {
        "_type": "Error",
        "message": "timeout",
        "do_not_reconnect": False,
        "rid": "1",
    },
    "GetRoomUsersResponse": {
        "_type": "GetRoomUsersResponse",
        "content": [
            [
                {"id": "u1", "username": "test"},
                {"x": 1.0, "y": 2.0, "z": 3.0, "facing": "FrontRight"},
            ],
            [
                {"id": "u2", "username": "test2"},
                {"x": 1.0, "y": 2.0, "z": 3.0, "facing": "FrontRight"},
            ],
        ],
        "rid": "1",
    },
    "GetWalletResponse": {
        "_type": "GetWalletResponse",
        "content": [{"type": "gold", "amount": 100}],
        "rid": "1",
    },
    "GetBackpackResponse": {
        "_type": "GetBackpackResponse",
        "backpack": {"item1": 1},
        "rid": "1",
    },
    "ChangeBackpackResponse": {"_type": "ChangeBackpackResponse", "rid": "1"},
    "GetRoomPrivilegeResponse": {
        "_type": "GetRoomPrivilegeResponse",
        "content": {"moderator": True, "designer": False},
        "rid": "1",
    },
    "CheckVoiceChatResponse": {
        "_type": "CheckVoiceChatResponse",
        "seconds_left": 10,
        "auto_speakers": [],
        "users": {},
        "rid": "1",
    },
    "GetUserOutfitResponse": {
        "_type": "GetUserOutfitResponse",
        "outfit": [],
        "rid": "1",
    },
    "GetConversationsResponse": {
        "_type": "GetConversationsResponse",
        "conversations": [],
        "not_joined": 0,
        "rid": "1",
    },
    "SendMessageResponse": {"_type": "SendMessageResponse", "rid": "1"},
    "SendBulkMessageResponse": {"_type": "SendBulkMessageResponse", "rid": "1"},
    "GetMessagesResponse": {"_type": "GetMessagesResponse", "messages": [], "rid": "1"},
    "LeaveConversationResponse": {"_type": "LeaveConversationResponse", "rid": "1"},
    "BuyVoiceTimeResponse": {
        "_type": "BuyVoiceTimeResponse",
        "result": "ok",
        "rid": "1",
    },
    "BuyRoomBoostResponse": {
        "_type": "BuyRoomBoostResponse",
        "result": "ok",
        "rid": "1",
    },
    "TipUserResponse": {"_type": "TipUserResponse", "result": "ok", "rid": "1"},
    "GetInventoryResponse": {"_type": "GetInventoryResponse", "items": [], "rid": "1"},
    "SetOutfitResponse": {"_type": "SetOutfitResponse", "rid": "1"},
    "BuyItemResponse": {"_type": "BuyItemResponse", "result": "ok", "rid": "1"},
    "MessageMediaResponse": {
        "_type": "MessageMediaResponse",
        "media": None,
        "uploadUrl": None,
        "thumbnailUploadUrl": None,
        "rid": "1",
    },
    "KeepaliveResponse": {"_type": "KeepaliveResponse", "rid": "1"},
    "ChatResponse": {"_type": "ChatResponse", "rid": "1"},
    "EmoteResponse": {"_type": "EmoteResponse", "rid": "1"},
    "ReactionResponse": {"_type": "ReactionResponse", "rid": "1"},
    "IndicatorResponse": {"_type": "IndicatorResponse", "rid": "1"},
    "ChannelResponse": {"_type": "ChannelResponse", "rid": "1"},
    "TeleportResponse": {"_type": "TeleportResponse", "rid": "1"},
    "FloorHitResponse": {"_type": "FloorHitResponse", "rid": "1"},
    "AnchorHitResponse": {"_type": "AnchorHitResponse", "rid": "1"},
    "ModerateRoomResponse": {"_type": "ModerateRoomResponse", "rid": "1"},
    "ChangeRoomPrivilegeResponse": {"_type": "ChangeRoomPrivilegeResponse", "rid": "1"},
    "MoveUserToRoomResponse": {"_type": "MoveUserToRoomResponse", "rid": "1"},
    "InviteSpeakerResponse": {"_type": "InviteSpeakerResponse", "rid": "1"},
    "RemoveSpeakerResponse": {"_type": "RemoveSpeakerResponse", "rid": "1"},
}
