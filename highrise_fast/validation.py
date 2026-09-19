"""
highrise_fast/validation.py
Perfect Official-Compatible Native Validator.
Mimics cattrs structuring behavior exactly (strict on structure/keys, lenient on scalars).
"""
from __future__ import annotations
from typing import Any

__all__ = [
    "HighriseFastValidationError",
    "ValidationErrorDetail",
    "validate_server_message",
]


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
# TYPE CHECKERS (mimic cattrs strict typing)
# ─────────────────────────────────────────────────────────────

def _require_str(data: dict, key: str, path: str) -> str:
    """Require a string field."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if not isinstance(val, str):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be str, got {_type_name(val)}"
        )
    return val


def _require_int(data: dict, key: str, path: str) -> int:
    """Require an integer field. Rejects bool and float."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if isinstance(val, bool) or not isinstance(val, int):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int, got {_type_name(val)}"
        )
    return val


def _require_float(data: dict, key: str, path: str) -> float:
    """Require a numeric field (int or float). Rejects bool."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be float, got {_type_name(val)}"
        )
    return val


def _require_bool(data: dict, key: str, path: str) -> bool:
    """Require a boolean field."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if not isinstance(val, bool):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be bool, got {_type_name(val)}"
        )
    return val


def _require_dict(data: dict, key: str, path: str) -> dict | None:
    """Require a dict field. None is accepted (for Optional fields)."""
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if val is None:
        return None
    if not isinstance(val, dict):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be dict, got {_type_name(val)}"
        )
    return val


def _is_empty_iterable(val: Any) -> bool:
    """Check if value is an empty string or empty dict (cattrs treats these as empty lists)."""
    if isinstance(val, str) and len(val) == 0:
        return True
    if isinstance(val, dict) and len(val) == 0:
        return True
    return False


def _check_list_tuples(data: dict, key: str, path: str, expected_len: int) -> list:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    # Official SDK accepts empty strings and empty dicts as empty lists (cattrs quirk)
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
    # Official SDK accepts empty strings and empty dicts as empty lists (cattrs quirk)
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
# ENTITY VALIDATORS (with proper type checking)
# ─────────────────────────────────────────────────────────────

def _validate_user(d: dict, path: str):
    _require_str(d, "id", path)
    _require_str(d, "username", path)


def _validate_position(d: dict, path: str):
    _require_float(d, "x", path)
    _require_float(d, "y", path)
    _require_float(d, "z", path)
    # 'facing' is OPTIONAL in the official SDK (has a default value)
    if "facing" in d:
        _require_str(d, "facing", path)


def _validate_currency_item(d: dict, path: str):
    _require_str(d, "type", path)
    _require_int(d, "amount", path)


# ─────────────────────────────────────────────────────────────
# MESSAGE VALIDATORS (with proper type checking)
# ─────────────────────────────────────────────────────────────

def _validate_chat_event(p: dict):
    u = _require_dict(p, "user", "$")
    if u is not None:
        _validate_user(u, "$.user")
    _require_str(p, "message", "$")
    _require_bool(p, "whisper", "$")


def _validate_user_joined(p: dict):
    u = _require_dict(p, "user", "$")
    if u is not None:
        _validate_user(u, "$.user")
    pos = _require_dict(p, "position", "$")
    if pos is not None:
        _validate_position(pos, "$.position")


def _validate_user_left(p: dict):
    u = _require_dict(p, "user", "$")
    if u is not None:
        _validate_user(u, "$.user")


def _validate_user_moved(p: dict):
    u = _require_dict(p, "user", "$")
    if u is not None:
        _validate_user(u, "$.user")
    pos = _require_dict(p, "position", "$")
    if pos is not None:
        _validate_position(pos, "$.position")


def _validate_emote(p: dict):
    u = _require_dict(p, "user", "$")
    if u is not None:
        _validate_user(u, "$.user")
    _require_str(p, "emote_id", "$")
    # receiver is Optional[User] - accepts None or dict
    _require_dict(p, "receiver", "$")


def _validate_reaction(p: dict):
    u = _require_dict(p, "user", "$")
    if u is not None:
        _validate_user(u, "$.user")
    _require_str(p, "reaction", "$")


def _validate_tip(p: dict):
    s = _require_dict(p, "sender", "$")
    if s is not None:
        _validate_user(s, "$.sender")
    r = _require_dict(p, "receiver", "$")
    if r is not None:
        _validate_user(r, "$.receiver")
    i = _require_dict(p, "item", "$")
    if i is not None:
        _validate_currency_item(i, "$.item")


def _validate_voice(p: dict):
    users = _check_list_tuples(p, "users", "$", 2)
    for i, row in enumerate(users):
        if isinstance(row[0], dict):
            _validate_user(row[0], f"$.users[{i}][0]")
        # Second element must be a string
        if not isinstance(row[1], str):
            raise HighriseFastValidationError(
                f"ClassValidationError: $.users[{i}][1] must be str, got {_type_name(row[1])}"
            )
    _require_int(p, "seconds_left", "$")


def _validate_channel(p: dict):
    _require_str(p, "sender_id", "$")
    _require_str(p, "msg", "$")


def _validate_moderated(p: dict):
    _require_str(p, "moderatorId", "$")
    _require_str(p, "targetUserId", "$")
    _require_str(p, "moderationType", "$")
    _require_int(p, "duration", "$")


def _validate_error(p: dict):
    _require_str(p, "message", "$")
    _require_bool(p, "do_not_reconnect", "$")
    _require_str(p, "rid", "$")


def _validate_wallet(p: dict):
    content = _check_list_dicts(p, "content", "$")
    for i, item in enumerate(content):
        _validate_currency_item(item, f"$.content[{i}]")
    _require_str(p, "rid", "$")


def _validate_room_users(p: dict):
    content = _check_list_tuples(p, "content", "$", 2)
    for i, row in enumerate(content):
        if isinstance(row[0], dict):
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