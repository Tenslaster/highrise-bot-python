"""
highrise_fast/validation.py

Official-compatible native validator.

This version is tuned to behave like the official SDK / cattrs JSON pipeline.

Latest fixes:
- GetRoomUsersResponse.content must contain at least 2 entries.
- RoomModeratedEvent.duration must be present, but may be null.
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
    def __init__(
        self,
        path: str,
        message: str,
        expected: str = "",
        got: str = "",
        value: Any = None,
    ):
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
        return "highrise_fast strict validation failed:\n" + "\n".join(
            f"  - {e.render()}" for e in self.errors
        )

    def __str__(self) -> str:
        return self.render()


def _type_name(value: Any) -> str:
    return type(value).__name__


# ─────────────────────────────────────────────────────────────
# EMPTY ITERABLE SUPPORT
# ─────────────────────────────────────────────────────────────


def _is_empty_iterable(value: Any) -> bool:
    """
    Some official converters can treat empty string / empty dict as an empty list
    before applying list validators.

    For GetRoomUsersResponse we still reject those cases by enforcing a minimum
    length afterwards.
    """
    if isinstance(value, str) and len(value) == 0:
        return True
    if isinstance(value, dict) and len(value) == 0:
        return True
    return False


# ─────────────────────────────────────────────────────────────
# SCALAR COERCION
# ─────────────────────────────────────────────────────────────


def _require_str(data: dict, key: str, path: str) -> str:
    """
    Required string field.
    Official pipeline coerces JSON values to str.
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    return str(data[key])


def _require_int(data: dict, key: str, path: str) -> int:
    """
    Required int field.

    Accepts:
    - int
    - float, truncated by int()
    - bool
    - numeric strings accepted by int()

    Rejects:
    - null
    - list
    - dict
    - invalid strings
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    value = data[key]

    if value is None or isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible, got {_type_name(value)}"
        )

    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible, got {_type_name(value)}"
        )


def _require_float(data: dict, key: str, path: str) -> float:
    """
    Required float field.

    Accepts:
    - int
    - float
    - bool
    - numeric strings accepted by float()

    Rejects:
    - null
    - list
    - dict
    - invalid strings
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    value = data[key]

    if value is None or isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be float-compatible, got {_type_name(value)}"
        )

    try:
        return float(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be float-compatible, got {_type_name(value)}"
        )


def _require_bool(data: dict, key: str, path: str) -> bool:
    """
    Required bool field.
    Official pipeline coerces JSON values via bool().
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    return bool(data[key])


def _require_literal(data: dict, key: str, path: str, allowed: set[str]) -> str:
    """
    Required Literal field.
    Must be exactly one of the allowed strings.
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    value = data[key]

    if not isinstance(value, str) or value not in allowed:
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be one of {sorted(allowed)}, got {value!r}"
        )

    return value


def _require_optional_literal(
    data: dict,
    key: str,
    path: str,
    allowed: set[str],
) -> str | None:
    """
    Optional Literal field.

    Missing is allowed.
    If present, must be exactly one of the allowed strings.
    """
    if key not in data:
        return None

    value = data[key]

    if not isinstance(value, str) or value not in allowed:
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be one of {sorted(allowed)}, got {value!r}"
        )

    return value


# ─────────────────────────────────────────────────────────────
# DICT FIELDS
# ─────────────────────────────────────────────────────────────


def _require_dict(data: dict, key: str, path: str) -> dict:
    """
    Required object field.
    Must be a JSON object, not null.
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    value = data[key]

    if not isinstance(value, dict):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be dict, got {_type_name(value)}"
        )

    return value


def _require_optional_dict(data: dict, key: str, path: str) -> dict | None:
    """
    Optional object field.
    Missing or null becomes None.
    If present, must be dict.
    """
    if key not in data:
        return None

    value = data[key]

    if value is None:
        return None

    if not isinstance(value, dict):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be dict or null, got {_type_name(value)}"
        )

    return value


def _require_optional_str(data: dict, key: str, path: str) -> str | None:
    """
    Optional string field.
    Missing or null becomes None.
    Other values are coerced to str.
    """
    if key not in data:
        return None

    value = data[key]

    if value is None:
        return None

    return str(value)


def _require_optional_int(data: dict, key: str, path: str) -> int | None:
    """
    Optional int field.

    Missing or null becomes None.
    Other values use int coercion.
    """
    if key not in data:
        return None

    value = data[key]

    if value is None:
        return None

    if isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible or null, got {_type_name(value)}"
        )

    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible or null, got {_type_name(value)}"
        )


def _require_nullable_int(data: dict, key: str, path: str) -> int | None:
    """
    Required nullable int field.

    Key must be present.
    Value may be null.
    Non-null values use int coercion.
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    value = data[key]

    if value is None:
        return None

    if isinstance(value, (list, dict)):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible or null, got {_type_name(value)}"
        )

    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be int-compatible or null, got {_type_name(value)}"
        )


def _require_default_bool(data: dict, key: str, path: str) -> bool:
    """
    Bool field with default behavior.
    Missing is allowed and becomes False.
    Present values are coerced via bool().
    """
    if key not in data:
        return False

    return bool(data[key])


def _require_default_optional_str(data: dict, key: str, path: str) -> str | None:
    """
    Optional string field with default behavior.
    Missing is allowed.
    """
    return _require_optional_str(data, key, path)


# ─────────────────────────────────────────────────────────────
# LIST FIELDS
# ─────────────────────────────────────────────────────────────


def _check_list(data: dict, key: str, path: str) -> list:
    """
    Required list field.

    Accepts:
    - JSON array
    - empty string as empty list
    - empty object as empty list

    Specific message validators may impose extra constraints afterwards,
    such as minimum length.
    """
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")

    value = data[key]

    if _is_empty_iterable(value):
        return []

    if not isinstance(value, list):
        raise HighriseFastValidationError(
            f"ClassValidationError: {path}.{key} must be list, got {_type_name(value)}"
        )

    return value


def _check_list_dicts(data: dict, key: str, path: str) -> list:
    """
    Required list of objects.
    Each item must be a JSON object.
    """
    value = _check_list(data, key, path)

    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise HighriseFastValidationError(
                f"ClassValidationError: {path}.{key}[{i}] must be dict, got {_type_name(item)}"
            )

    return value


def _check_list_tuples(data: dict, key: str, path: str, expected_len: int) -> list:
    """
    Required list of tuple-like rows.

    JSON arrays are used as tuples.
    Each row must have expected_len.
    The first entry must be a JSON object because all current tuple models
    start with an entity object.
    """
    value = _check_list(data, key, path)

    for i, row in enumerate(value):
        row_path = f"{path}.{key}[{i}]"

        if not isinstance(row, (list, tuple)):
            raise HighriseFastValidationError(
                f"ClassValidationError: {row_path} must be list, got {_type_name(row)}"
            )

        if len(row) != expected_len:
            raise HighriseFastValidationError(
                f"ClassValidationError: {row_path} length {len(row)} != {expected_len}"
            )

        if not isinstance(row[0], dict):
            raise HighriseFastValidationError(
                f"ClassValidationError: {row_path}[0] must be dict, got {_type_name(row[0])}"
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

    # facing is optional / has default in the official model,
    # but if present it must be valid.
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
                f"ClassValidationError: $.users[{i}][1] must be one of "
                f"{sorted(VOICE_STATUS_VALUES)}, got {status!r}"
            )

    _require_int(payload, "seconds_left", "$")


def _validate_channel(payload: dict) -> None:
    _require_str(payload, "sender_id", "$")
    _require_str(payload, "msg", "$")


def _validate_moderated(payload: dict) -> None:
    _require_str(payload, "moderatorId", "$")
    _require_str(payload, "targetUserId", "$")
    _require_literal(payload, "moderationType", "$", MODERATION_VALUES)

    # Official requires duration to be present, but it may be null.
    _require_nullable_int(payload, "duration", "$")


def _validate_error(payload: dict) -> None:
    _require_str(payload, "message", "$")
    _require_default_bool(payload, "do_not_reconnect", "$")
    _require_default_optional_str(payload, "rid", "$")


def _validate_wallet(payload: dict) -> None:
    content = _check_list_dicts(payload, "content", "$")

    for i, item in enumerate(content):
        _validate_currency_item(item, f"$.content[{i}]")

    _require_str(payload, "rid", "$")


def _validate_room_users(payload: dict) -> None:
    content = _check_list_tuples(payload, "content", "$", 2)

    # Official rejects empty content and also rejects a single-entry content list.
    # Duplicated / larger content lists are accepted.
    if len(content) < 2:
        raise HighriseFastValidationError(
            "ClassValidationError: $.content must contain at least 2 entries"
        )

    for i, row in enumerate(content):
        _validate_user(row[0], f"$.content[{i}][0]")

        position = row[1]

        if not isinstance(position, dict):
            raise HighriseFastValidationError(
                f"ClassValidationError: $.content[{i}][1] must be dict, got {_type_name(position)}"
            )

        _validate_position(position, f"$.content[{i}][1]")


# ─────────────────────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────────────────────

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


def validate_server_message(data: Any, **kwargs: Any) -> dict:
    """
    Validate one incoming Highrise server message payload.

    Returns the original payload dict if validation succeeds.
    Raises HighriseFastValidationError if validation fails.
    """
    if not isinstance(data, dict):
        raise HighriseFastValidationError(
            f"payload must be an object, got {_type_name(data)}"
        )

    if "_type" not in data:
        raise HighriseFastValidationError("KeyError: '_type'")

    message_type = data["_type"]

    handler = _DISPATCH.get(message_type)
    if handler is None:
        raise HighriseFastValidationError(
            f"ClassValidationError: unknown _type {message_type!r}"
        )

    handler(data)

    return data
