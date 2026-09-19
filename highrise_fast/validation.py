"""
highrise_fast/validation.py
Perfect Official-Compatible Native Validator.
Mimics cattrs.preconf.json structuring behavior exactly.
"""
from __future__ import annotations
from typing import Any

__all__ = [
    "HighriseFastValidationError",
    "ValidationErrorDetail",
    "validate_server_message",
]

# Valid Literal values from the official SDK
FACING_VALUES = {"FrontRight", "FrontLeft", "BackRight", "BackLeft"}
MODERATION_VALUES = {"kick", "mute", "unmute", "ban", "unban"}
REACTION_VALUES = {"clap", "heart", "thumbs", "wave", "wink"}
VOICE_STATUS_VALUES = {"voice", "muted"}


class ValidationErrorDetail:
    def __init__(self, path: str, message: str, expected: str = "", got: str = "", value: Any = None):
        self.path = path
        self.message = message
        self.expected = expected
        self.got = got
        self.value = value

    def render(self) -> str:
        return f"{self.path}: {self.message} (expected {self.expected}, got {self.got})"


class HighriseFastValidationError(ValueError):
    def __init__(self, errors: list[ValidationErrorDetail] | str):
        if isinstance(errors, str):
            self.errors = [ValidationErrorDetail("$", errors)]
        else:
            self.errors = errors
        super().__init__(self.render())

    def render(self) -> str:
        return "highrise_fast strict validation failed:\n" + "\n".join(f"  - {e.render()}" for e in self.errors)

    def __str__(self) -> str:
        return self.render()


def _type_name(v: Any) -> str:
    return type(v).__name__


# ─────────────────────────────────────────────────────────────
# SCALAR COERCION (mimics cattrs.preconf.json)
# ─────────────────────────────────────────────────────────────

def _require_str(data: dict, key: str, path: str) -> str:
    """str fields: cattrs coerces ANY JSON value via str()."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    return str(data[key])


def _require_int(data: dict, key: str, path: str) -> int:
    """int fields: accepts int, float (truncate), bool, valid str. Rejects null/list/dict/invalid str."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if val is None or isinstance(val, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible, got {_type_name(val)}"
        )
    try:
        return int(val)
    except (ValueError, TypeError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible, got {_type_name(val)}"
        )


def _require_float(data: dict, key: str, path: str) -> float:
    """float fields: accepts int, float, bool, valid str. Rejects null/list/dict/invalid str."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if val is None or isinstance(val, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be float-compatible, got {_type_name(val)}"
        )
    try:
        return float(val)
    except (ValueError, TypeError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be float-compatible, got {_type_name(val)}"
        )


def _require_bool(data: dict, key: str, path: str) -> bool:
    """bool fields: cattrs coerces ANY JSON value via bool()."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    return bool(data[key])


def _require_literal(data: dict, key: str, path: str, allowed: set[str]) -> str:
    """Literal fields: value must be EXACTLY one of the allowed strings. No coercion."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if not isinstance(val, str) or val not in allowed:
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be one of {sorted(allowed)}, got {repr(val)}"
        )
    return val


def _require_optional_literal(data: dict, key: str, path: str, allowed: set[str]) -> str | None:
    """Optional Literal field: can be missing, but if present must be valid."""
    if key not in data:
        return None
    val = data[key]
    if not isinstance(val, str) or val not in allowed:
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be one of {sorted(allowed)}, got {repr(val)}"
        )
    return val


# ─────────────────────────────────────────────────────────────
# DICT FIELDS
# ─────────────────────────────────────────────────────────────

def _require_dict(data: dict, key: str, path: str) -> dict:
    """Required dict field: must be dict, NOT null."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if not isinstance(val, dict):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be dict, got {_type_name(val)}"
        )
    return val


def _require_optional_dict(data: dict, key: str, path: str) -> dict | None:
    """Optional dict field: can be None or dict."""
    if key not in data:
        return None
    val = data[key]
    if val is None:
        return None
    if not isinstance(val, dict):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be dict or null, got {_type_name(val)}"
        )
    return val


def _require_optional_str(data: dict, key: str, path: str) -> str | None:
    """Optional str field: if null returns None, otherwise coerces to str."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if val is None:
        return None
    return str(val)


def _require_optional_int(data: dict, key: str, path: str) -> int | None:
    """Optional int field: if null returns None, otherwise coerces to int."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible, got {_type_name(val)}"
        )
    try:
        return int(val)
    except (ValueError, TypeError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible, got {_type_name(val)}"
        )


def _require_default_bool(data: dict, key: str, path: str) -> bool:
    """Bool field with default: can be missing."""
    if key not in data:
        return False
    return bool(data[key])


def _require_default_optional_str(data: dict, key: str, path: str) -> str | None:
    """Optional str field with default: can be missing."""
    if key not in data:
        return None
    val = data[key]
    if val is None:
        return None
    return str(val)


# ─────────────────────────────────────────────────────────────
# LIST FIELDS
# ─────────────────────────────────────────────────────────────

def _is_empty_iterable(val: Any) -> bool:
    if isinstance(val, str) and len(val) == 0:
        return True
    if isinstance(val, dict) and len(val) == 0:
        return True
    return False


def _check_list_tuples(data: dict, key: str, path: str, expected_len: int) -> list:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if _is_empty_iterable(val):
        return []
    if not isinstance(val, list):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be list, got {_type_name(val)}"
        )
    for i, row in enumerate(val):
        if not isinstance(row, (list, tuple)):
            raise HighriseFastValidationError(
                f"ClassValidationError: {path}.{key}[{i}] must be tuple, got {_type_name(row)}"
            )
        if len(row) != expected_len:
            raise HighriseFastValidationError(
                f"ClassValidationError: {path}.{key}[{i}] length {len(row)} != {expected_len}"
            )
        if not isinstance(row[0], dict):
            raise HighriseFastValidationError(
                f"ClassValidationError: {path}.{key}[{i}][0] must be dict, got {_type_name(row[0])}"
            )
    return val


def _check_list_dicts(data: dict, key: str, path: str) -> list:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if _is_empty_iterable(val):
        return []
    if not isinstance(val, list):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be list, got {_type_name(val)}"
        )
    for i, item in enumerate(val):
        if not isinstance(item, dict):
            raise HighriseFastValidationError(
                f"ClassValidationError: {path}.{key}[{i}] must be dict, got {_type_name(item)}"
            )
    return val


# ─────────────────────────────────────────────────────────────
# ENTITY VALIDATORS
# ─────────────────────────────────────────────────────────────

def _validate_user(d: dict, path: str):
    _require_str(d, "id", path)
    _require_str(d, "username", path)


def _validate_position(d: dict, path: str):
    _require_float(d, "x", path)
    _require_float(d, "y", path)
    _require_float(d, "z", path)
    # facing is optional (has default) but if present must be valid Literal
    _require_optional_literal(d, "facing", path, FACING_VALUES)


def _validate_currency_item(d: dict, path: str):
    _require_str(d, "type", path)
    _require_int(d, "amount", path)


# ─────────────────────────────────────────────────────────────
# MESSAGE VALIDATORS
# ─────────────────────────────────────────────────────────────

def _validate_chat_event(p: dict):
    u = _require_dict(p, "user", "$")
    _validate_user(u, "$.user")
    _require_str(p, "message", "$")
    _require_bool(p, "whisper", "$")


def _validate_user_joined(p: dict):
    u = _require_dict(p, "user", "$")
    _validate_user(u, "$.user")
    pos = _require_dict(p, "position", "$")
    _validate_position(pos, "$.position")


def _validate_user_left(p: dict):
    u = _require_dict(p, "user", "$")
    _validate_user(u, "$.user")


def _validate_user_moved(p: dict):
    u = _require_dict(p, "user", "$")
    _validate_user(u, "$.user")
    pos = _require_dict(p, "position", "$")
    _validate_position(pos, "$.position")


def _validate_emote(p: dict):
    u = _require_dict(p, "user", "$")
    _validate_user(u, "$.user")
    _require_str(p, "emote_id", "$")
    # receiver is Optional[User] in EmoteEvent
    r = _require_optional_dict(p, "receiver", "$")
    if r is not None:
        _validate_user(r, "$.receiver")


def _validate_reaction(p: dict):
    u = _require_dict(p, "user", "$")
    _validate_user(u, "$.user")
    _require_literal(p, "reaction", "$", REACTION_VALUES)
    r = _require_dict(p, "receiver", "$")
    _validate_user(r, "$.receiver")


def _validate_tip(p: dict):
    s = _require_dict(p, "sender", "$")
    _validate_user(s, "$.sender")
    r = _require_dict(p, "receiver", "$")
    _validate_user(r, "$.receiver")
    i = _require_dict(p, "item", "$")
    _validate_currency_item(i, "$.item")


def _validate_voice(p: dict):
    users = _check_list_tuples(p, "users", "$", 2)
    for i, row in enumerate(users):
        _validate_user(row[0], f"$.users[{i}][0]")
        # Second element must be valid Literal
        val = row[1]
        if not isinstance(val, str) or val not in VOICE_STATUS_VALUES:
            raise HighriseFastValidationError(
                f"ClassValidationError: $.users[{i}][1] must be one of {sorted(VOICE_STATUS_VALUES)}, got {repr(val)}"
            )
    _require_int(p, "seconds_left", "$")


def _validate_channel(p: dict):
    _require_str(p, "sender_id", "$")
    _require_str(p, "msg", "$")


def _validate_moderated(p: dict):
    _require_str(p, "moderatorId", "$")
    _require_str(p, "targetUserId", "$")
    _require_literal(p, "moderationType", "$", MODERATION_VALUES)
    _require_optional_int(p, "duration", "$")


def _validate_error(p: dict):
    _require_str(p, "message", "$")
    _require_default_bool(p, "do_not_reconnect", "$")
    _require_default_optional_str(p, "rid", "$")


def _validate_wallet(p: dict):
    content = _check_list_dicts(p, "content", "$")
    for i, item in enumerate(content):
        _validate_currency_item(item, f"$.content[{i}]")
    _require_str(p, "rid", "$")


def _validate_room_users(p: dict):
    content = _check_list_tuples(p, "content", "$", 2)
    for i, row in enumerate(content):
        _validate_user(row[0], f"$.content[{i}][0]")
        if isinstance(row[1], dict):
            _validate_position(row[1], f"$.content[{i}][1]")


_DISPATCH = {
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
    "Error": _validate_error,
    "GetWalletResponse": _validate_wallet,
    "GetRoomUsersResponse": _validate_room_users,
}


def validate_server_message(data: Any, **kwargs) -> dict:
    if not isinstance(data, dict):
        raise HighriseFastValidationError(
            f"payload must be an object, got {_type_name(data)}"
        )
    if "_type" not in data:
        raise HighriseFastValidationError("KeyError: '_type'")
    t = data["_type"]
    handler = _DISPATCH.get(t)
    if handler is None:
        raise HighriseFastValidationError(f"ClassValidationError: unknown _type '{t}'")
    handler(data)
    return data