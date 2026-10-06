"""Fast structural and semantic validation helpers for Highrise server messages."""
from __future__ import annotations

import copy
import json
import math
from typing import Any

__all__ = [
    "BASE_PAYLOADS",
    "HighriseFastValidationError",
    "ReasonCode",
    "ValidationErrorDetail",
    "validate_server_message",
]


FACING_VALUES = {"FrontRight", "FrontLeft", "BackRight", "BackLeft"}

MODERATION_VALUES = {"kick", "mute", "unmute", "ban", "unban"}

REACTION_VALUES = {"clap", "heart", "thumbs", "wave", "wink"}

VOICE_STATUS_VALUES = {"voice", "muted"}


class ReasonCode:
    """Machine-readable validation failure reason codes."""
    MISSING_FIELD = "MISSING_FIELD"

    WRONG_TYPE = "WRONG_TYPE"

    UNKNOWN_TYPE = "UNKNOWN_TYPE"

    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"

    INVALID_LENGTH = "INVALID_LENGTH"

    UNKNOWN_ERROR = "UNKNOWN_ERROR"


def _got_name(value: Any) -> str:
    """Return a short JSON-like type name for error messages."""

    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return "int"

    if isinstance(value, float):
        return "float"

    if isinstance(value, str):
        return "empty-string" if value == "" else "string"

    if isinstance(value, (list, tuple)):
        return "list"

    if isinstance(value, dict):
        return "dict"

    return type(value).__name__.lower()


def _short_value(value: Any, limit: int = 120) -> str:
    """Return a shortened repr for error messages."""

    text = repr(value)

    return text if len(text) <= limit else text[: limit - 3] + "..."


class ValidationErrorDetail:
    """Single validation failure detail."""
    __slots__ = ("expected", "got", "message", "path", "reason_code", "value")

    def __init__(
        self,
        path: str,
        message: str,
        expected: str = "",
        got: str = "",
        value: Any = None,
        reason_code: str = ReasonCode.UNKNOWN_ERROR,
    ):
        """Initialize the instance."""

        self.path = path

        self.message = message

        self.expected = expected

        self.got = got

        self.value = value

        self.reason_code = reason_code

    def render(self) -> str:
        """Render."""

        base = f"[{self.reason_code}] field {self.path}: {self.message}"

        extras: list[str] = []

        if self.expected:
            extras.append(f"expected {self.expected}")

        if self.got:
            extras.append(f"got {self.got}")

        if self.value is not None and not isinstance(self.value, (dict, list)):
            extras.append(f"value={_short_value(self.value)}")

        if extras:
            base += " (" + ", ".join(extras) + ")"

        return base

    def to_dict(self) -> dict:
        """To dict."""

        return {
            "path": self.path,
            "message": self.message,
            "expected": self.expected,
            "got": self.got,
            "value": self.value,
            "reason_code": self.reason_code,
        }

    def __repr__(self) -> str:
        """Return a developer-friendly representation."""

        return f"<ValidationErrorDetail {self.render()}>"


class HighriseFastValidationError(ValueError):
    """Validation error containing one or more structured details."""
    def __init__(self, errors: list[ValidationErrorDetail] | str, payload: Any = None):
        """Initialize the instance."""

        if isinstance(errors, str):
            self.errors = [ValidationErrorDetail("$", errors)]

        else:
            self.errors = errors

        self.payload = payload

        super().__init__(self.render())

    def render(self) -> str:
        """Render."""

        lines = ["highrise_fast validation failed:"]

        if not self.errors:
            lines.append("  - unknown validation error")

            return "\n".join(lines)

        for error in self.errors:
            lines.append(f"  - {error.render()}")

        return "\n".join(lines)

    def short(self) -> str:
        """Short."""

        if not self.errors:
            return "validation failed"

        if len(self.errors) == 1:
            e = self.errors[0]

            return f"{e.path}: {e.message} [{e.reason_code}]"

        first = self.errors[0]

        return f"{len(self.errors)} errors; first: {first.path}: {first.message} [{first.reason_code}]"

    def to_dict(self) -> dict:
        """To dict."""

        return {"errors": [e.to_dict() for e in self.errors], "payload": self.payload}

    def verbose(self) -> str:
        """Verbose."""

        payload_str = "<no payload captured>"

        if self.payload is not None:
            try:
                payload_str = json.dumps(
                    self.payload, indent=2, default=str, ensure_ascii=False
                )

            except (TypeError, ValueError):
                payload_str = repr(self.payload)

        return f"{self.render()}\n\n--- Rejected Payload ---\n{payload_str}"

    def __str__(self) -> str:
        """Return a human-readable string representation."""

        return self.render()


def _err(
    path: str,
    message: str,
    expected: str = "",
    got: str = "",
    value: Any = None,
    reason_code: str = ReasonCode.UNKNOWN_ERROR,
) -> HighriseFastValidationError:
    """Build a HighriseFastValidationError with one structured detail."""

    if reason_code == ReasonCode.MISSING_FIELD and not got:
        got = "missing"

    if not got and value is not None:
        got = _got_name(value)

    if reason_code == ReasonCode.MISSING_FIELD and "field" not in message.lower():
        message = f"{message} field"

    return HighriseFastValidationError(
        [
            ValidationErrorDetail(
                path=path,
                message=message,
                expected=expected,
                got=got,
                value=value,
                reason_code=reason_code,
            )
        ]
    )


def _require_str(data: dict, key: str, path: str) -> str:
    """Require a string field."""

    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required string",
            expected="str",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )

    value = data[key]

    if not isinstance(value, str):
        raise _err(
            f"{path}.{key}",
            "must be str",
            expected="str",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _bad_int(value: Any) -> bool:
    """True when value must never validate as an int.

    - bool: bool is a subclass of int, so isinstance(True, int) is True,
      but JSON ``true`` is not an integer.
    - Non-integral float: int(1.9) would silently truncate to 1.
      (Also rejects nan/inf, which crash or poison int().)
    """
    if isinstance(value, bool):
        return True
    if isinstance(value, float):
        return not value.is_integer()
    return False


def _require_int(data: dict, key: str, path: str) -> int:
    """Require an integer-compatible field."""
    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required int",
            expected="int",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )
    value = data[key]
    if value is None or isinstance(value, (list, dict)) or _bad_int(value):
        raise _err(
            f"{path}.{key}",
            "must be int-compatible",
            expected="int",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise _err(
            f"{path}.{key}",
            "must be int-compatible",
            expected="int",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        ) from None


def _require_float(data: dict, key: str, path: str) -> float:
    """Require a finite float-compatible field."""
    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required float",
            expected="float",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )
    value = data[key]
    if value is None or isinstance(value, bool) or isinstance(value, (list, dict)):
        raise _err(
            f"{path}.{key}",
            "must be float-compatible",
            expected="float",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )
    try:
        fval = float(value)
    except (ValueError, TypeError, OverflowError):
        raise _err(
            f"{path}.{key}",
            "must be float-compatible",
            expected="float",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        ) from None
    if not math.isfinite(fval):
        raise _err(
            f"{path}.{key}",
            "must be finite float",
            expected="finite float",
            got=str(fval),
            value=value,
            reason_code=ReasonCode.OUT_OF_BOUNDS,
        )
    return fval


def _require_bool(data: dict, key: str, path: str) -> bool:
    """Require a boolean field."""

    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required bool",
            expected="bool",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )

    value = data[key]

    if not isinstance(value, bool):
        raise _err(
            f"{path}.{key}",
            "must be bool",
            expected="bool",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_literal(data: dict, key: str, path: str, allowed: set[str]) -> str:
    """Require a string field matching an allowed literal set."""

    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required literal",
            expected="literal",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )

    value = data[key]

    if not isinstance(value, str) or value not in allowed:
        raise _err(
            f"{path}.{key}",
            f"must be one of {sorted(allowed)}",
            expected="literal",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_optional_literal(
    data: dict, key: str, path: str, allowed: set[str]
) -> str | None:
    """Require an optional string field matching an allowed literal set."""

    if key not in data:
        return None

    value = data[key]

    if not isinstance(value, str) or value not in allowed:
        raise _err(
            f"{path}.{key}",
            f"must be one of {sorted(allowed)}",
            expected="literal",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_dict(data: dict, key: str, path: str) -> dict:
    """Require a dict field."""

    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required dict",
            expected="dict",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )

    value = data[key]

    if not isinstance(value, dict):
        raise _err(
            f"{path}.{key}",
            "must be dict",
            expected="dict",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_optional_dict(data: dict, key: str, path: str) -> dict | None:
    """Require an optional dict field."""

    if key not in data:
        return None

    value = data[key]

    if value is None:
        return None

    if not isinstance(value, dict):
        raise _err(
            f"{path}.{key}",
            "must be dict or null",
            expected="dict",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_optional_str(data: dict, key: str, path: str) -> str | None:
    """Require an optional string field."""

    if key not in data:
        return None

    value = data[key]

    if value is None:
        return None

    if not isinstance(value, str):
        raise _err(
            f"{path}.{key}",
            "must be str or null",
            expected="str",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_optional_int(data: dict, key: str, path: str) -> int | None:
    """Require an optional integer-compatible field."""
    if key not in data:
        return None
    value = data[key]
    if value is None:
        return None
    if isinstance(value, (list, dict)) or _bad_int(value):
        raise _err(
            f"{path}.{key}",
            "must be int-compatible or null",
            expected="int",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise _err(
            f"{path}.{key}",
            "must be int-compatible or null",
            expected="int",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        ) from None


def _require_nullable_int(data: dict, key: str, path: str) -> int | None:
    """Require a nullable integer-compatible field."""
    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required nullable int",
            expected="int|null",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )
    value = data[key]
    if value is None:
        return None
    if isinstance(value, (list, dict)) or _bad_int(value):
        raise _err(
            f"{path}.{key}",
            "must be int-compatible or null",
            expected="int",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        raise _err(
            f"{path}.{key}",
            "must be int-compatible or null",
            expected="int",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        ) from None


def _require_default_bool(data: dict, key: str, path: str) -> bool:
    """Read a bool field with a False default."""

    if key not in data:
        return False

    value = data[key]

    if not isinstance(value, bool):
        raise _err(
            f"{path}.{key}",
            "must be bool",
            expected="bool",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _require_default_optional_str(data: dict, key: str, path: str) -> str | None:
    """Read an optional string field with a None default."""

    return _require_optional_str(data, key, path)


def _check_list(data: dict, key: str, path: str) -> list:
    """Require a list field."""

    if key not in data:
        raise _err(
            f"{path}.{key}",
            "missing required list",
            expected="list",
            got="missing",
            reason_code=ReasonCode.MISSING_FIELD,
        )

    value = data[key]

    if not isinstance(value, list):
        raise _err(
            f"{path}.{key}",
            "must be list",
            expected="list",
            got=_got_name(value),
            value=value,
            reason_code=ReasonCode.WRONG_TYPE,
        )

    return value


def _check_list_dicts(data: dict, key: str, path: str) -> list:
    """Require a list of dicts field."""

    value = _check_list(data, key, path)

    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise _err(
                f"{path}.{key}[{i}]",
                "must be dict",
                expected="dict",
                got=_got_name(item),
                value=item,
                reason_code=ReasonCode.WRONG_TYPE,
            )

    return value


def _check_list_tuples(data: dict, key: str, path: str, expected_len: int) -> list:
    """Require a list of fixed-length tuple-like rows."""

    value = _check_list(data, key, path)

    for i, row in enumerate(value):
        row_path = f"{path}.{key}[{i}]"

        if not isinstance(row, (list, tuple)):
            raise _err(
                row_path,
                "must be list/tuple",
                expected="list",
                got=_got_name(row),
                value=row,
                reason_code=ReasonCode.WRONG_TYPE,
            )

        if len(row) != expected_len:
            raise _err(
                row_path,
                f"length {len(row)} != {expected_len}",
                expected=str(expected_len),
                got=str(len(row)),
                value=row,
                reason_code=ReasonCode.INVALID_LENGTH,
            )

        if not isinstance(row[0], dict):
            raise _err(
                f"{row_path}[0]",
                "must be dict",
                expected="dict",
                got=_got_name(row[0]),
                value=row[0],
                reason_code=ReasonCode.WRONG_TYPE,
            )

    return value


def _validate_user(data: dict, path: str) -> None:
    """Validate a user object."""

    _require_str(data, "id", path)

    _require_str(data, "username", path)


def _validate_position(data: dict, path: str) -> None:
    """Validate a floor or anchor position."""

    if "entity_id" in data or "anchor_ix" in data:
        _require_str(data, "entity_id", path)

        _require_int(data, "anchor_ix", path)

        return

    _require_float(data, "x", path)

    _require_float(data, "y", path)

    _require_float(data, "z", path)

    _require_optional_literal(data, "facing", path, FACING_VALUES)


def _validate_currency_item(data: dict, path: str) -> None:
    """Validate a currency item."""

    _require_str(data, "type", path)

    _require_int(data, "amount", path)


def _validate_item_or_currency(data: dict, path: str) -> None:
    """Accept either a clothing Item shape or a CurrencyItem shape.

    CurrencyItem requires ``type`` and ``amount``. A clothing Item carries
    ``type``/``id`` and may omit ``amount`` (it defaults to 1), so
    ``amount`` is only enforced on the currency shape. Validation is
    deliberately slightly more permissive than the lenient parser: the
    validator's job is to drop malformed packets, not to police which
    legal shape the server chose.
    """
    _require_str(data, "type", path)

    if data.get("type") == "clothing" or "id" in data:
        _require_str(data, "id", path)
        _require_optional_int(data, "amount", path)
        _require_default_bool(data, "account_bound", path)
        _require_optional_int(data, "active_palette", path)
        return

    _require_int(data, "amount", path)


def _validate_chat_event(payload: dict) -> None:
    """Validate a ChatEvent payload."""

    user = _require_dict(payload, "user", "$")

    _validate_user(user, "$.user")

    _require_str(payload, "message", "$")

    _require_bool(payload, "whisper", "$")


def _validate_user_joined(payload: dict) -> None:
    """Validate a UserJoinedEvent payload."""
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")

    position = _require_optional_dict(payload, "position", "$")
    if position is not None:
        _validate_position(position, "$.position")


def _validate_user_left(payload: dict) -> None:
    """Validate a UserLeftEvent payload."""

    user = _require_dict(payload, "user", "$")

    _validate_user(user, "$.user")


def _validate_user_moved(payload: dict) -> None:
    """Validate a UserMovedEvent payload."""
    user = _require_dict(payload, "user", "$")
    _validate_user(user, "$.user")

    position = _require_optional_dict(payload, "position", "$")
    if position is not None:
        _validate_position(position, "$.position")


def _validate_emote(payload: dict) -> None:
    """Validate an EmoteEvent payload."""

    user = _require_dict(payload, "user", "$")

    _validate_user(user, "$.user")

    _require_str(payload, "emote_id", "$")

    receiver = _require_optional_dict(payload, "receiver", "$")

    if receiver is not None:
        _validate_user(receiver, "$.receiver")


def _validate_reaction(payload: dict) -> None:
    """Validate a ReactionEvent payload."""

    user = _require_dict(payload, "user", "$")

    _validate_user(user, "$.user")

    _require_literal(payload, "reaction", "$", REACTION_VALUES)

    receiver = _require_optional_dict(payload, "receiver", "$")

    if receiver is not None:

        _validate_user(receiver, "$.receiver")


def _validate_tip(payload: dict) -> None:
    """Validate a TipReactionEvent payload."""

    sender = _require_dict(payload, "sender", "$")

    _validate_user(sender, "$.sender")

    receiver = _require_dict(payload, "receiver", "$")

    _validate_user(receiver, "$.receiver")

    item = _require_optional_dict(payload, "item", "$")

    if item is not None:

        _validate_item_or_currency(item, "$.item")


def _validate_voice(payload: dict) -> None:
    """Validate a VoiceEvent payload."""
    if "users" in payload:
        users = _check_list_tuples(payload, "users", "$", 2)
        for i, row in enumerate(users):
            _validate_user(row[0], f"$.users[{i}][0]")
            status = row[1]
            if not isinstance(status, str) or status not in VOICE_STATUS_VALUES:
                raise _err(
                    f"$.users[{i}][1]",
                    f"must be one of {sorted(VOICE_STATUS_VALUES)}",
                    expected="literal",
                    got=_got_name(status),
                    value=status,
                    reason_code=ReasonCode.WRONG_TYPE,
                )
    if "seconds_left" in payload:
        _require_int(payload, "seconds_left", "$")


def _validate_channel(payload: dict) -> None:
    """Validate a ChannelEvent payload."""

    _require_str(payload, "sender_id", "$")

    _require_str(payload, "msg", "$")


def _validate_moderated(payload: dict) -> None:
    """Validate a RoomModeratedEvent payload."""

    _require_str(payload, "moderatorId", "$")

    _require_str(payload, "targetUserId", "$")

    _require_literal(payload, "moderationType", "$", MODERATION_VALUES)

    _require_optional_int(payload, "duration", "$")


def _validate_error(payload: dict) -> None:
    """Validate an Error payload."""

    _require_str(payload, "message", "$")

    _require_default_bool(payload, "do_not_reconnect", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_message_event(payload: dict) -> None:
    """Validate a MessageEvent payload."""

    _require_str(payload, "user_id", "$")

    _require_str(payload, "conversation_id", "$")

    _require_default_bool(payload, "is_new_conversation", "$")


def _validate_wallet(payload: dict) -> None:
    """Validate a GetWalletResponse payload."""

    content = _check_list_dicts(payload, "content", "$")

    for i, item in enumerate(content):
        _validate_currency_item(item, f"$.content[{i}]")

    _require_default_optional_str(payload, "rid", "$")


def _validate_room_users(payload: dict) -> None:
    """Validate a GetRoomUsersResponse payload."""

    content = _check_list_tuples(payload, "content", "$", 2)

    for i, row in enumerate(content):
        _validate_user(row[0], f"$.content[{i}][0]")

        position = row[1]

        if not isinstance(position, dict):
            raise _err(
                f"$.content[{i}][1]",
                "must be dict",
                expected="dict",
                got=_got_name(position),
                value=position,
                reason_code=ReasonCode.WRONG_TYPE,
            )

        _validate_position(position, f"$.content[{i}][1]")


def _validate_ack(payload: dict) -> None:
    """Validate a simple acknowledgement payload."""

    _require_default_optional_str(payload, "rid", "$")


def _validate_backpack(payload: dict) -> None:
    """Validate a GetBackpackResponse payload."""

    _require_dict(payload, "backpack", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_room_privilege(payload: dict) -> None:
    """Validate a GetRoomPrivilegeResponse payload."""

    _require_dict(payload, "content", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_voice_status(payload: dict) -> None:
    """Validate a CheckVoiceChatResponse payload."""
    _require_int(payload, "seconds_left", "$")

    auto_speakers = _check_list(payload, "auto_speakers", "$")
    for index, user_id in enumerate(auto_speakers):
        if not isinstance(user_id, str):
            raise _err(
                f"$.auto_speakers[{index}]",
                "must be str",
                expected="str",
                got=_got_name(user_id),
                value=user_id,
                reason_code=ReasonCode.WRONG_TYPE,
            )

    users = _require_dict(payload, "users", "$")
    for user_id, status in users.items():
        if not isinstance(user_id, str):
            raise _err(
                f"$.users[{user_id!r}]",
                "user ID must be str",
                expected="str",
                got=_got_name(user_id),
                value=user_id,
                reason_code=ReasonCode.WRONG_TYPE,
            )

        if not isinstance(status, str):
            raise _err(
                f"$.users[{user_id!r}]",
                "voice status must be str",
                expected="str",
                got=_got_name(status),
                value=status,
                reason_code=ReasonCode.WRONG_TYPE,
            )

    _require_default_optional_str(payload, "rid", "$")


def _validate_outfit(payload: dict) -> None:
    """Validate a GetUserOutfitResponse payload."""

    _check_list(payload, "outfit", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_conversations(payload: dict) -> None:
    """Validate a GetConversationsResponse payload."""

    _check_list(payload, "conversations", "$")

    _require_int(payload, "not_joined", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_messages(payload: dict) -> None:
    """Validate a GetMessagesResponse payload."""

    _check_list(payload, "messages", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_result_ack(payload: dict) -> None:
    """Validate a result acknowledgement payload."""

    _require_str(payload, "result", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_inventory(payload: dict) -> None:
    """Validate a GetInventoryResponse payload."""

    _check_list(payload, "items", "$")

    _require_default_optional_str(payload, "rid", "$")


def _validate_media(payload: dict) -> None:
    """Validate a MessageMediaResponse payload."""

    _require_default_optional_str(payload, "rid", "$")


def _validate_session_metadata(payload: dict) -> None:
    """Validate a SessionMetadata payload."""

    _require_str(payload, "user_id", "$")

    room_info = _require_dict(payload, "room_info", "$")

    _require_str(room_info, "owner_id", "$.room_info")

    _require_str(room_info, "room_name", "$.room_info")

    _require_optional_dict(payload, "rate_limits", "$")

    _require_optional_str(payload, "connection_id", "$")

    _require_optional_str(payload, "sdk_version", "$")


def _validate_semantic_position(data: dict, path: str) -> None:
    """Validate semantic map bounds for a position."""

    for coord in ("x", "y", "z"):
        val = data.get(coord)

        if val is None:
            continue

        try:
            fval = float(val)

        except (ValueError, TypeError):
            continue

        if not (-2000.0 <= fval <= 2000.0):
            raise _err(
                f"{path}.{coord}",
                "out of map bounds",
                expected="[-2000.0, 2000.0]",
                got=str(fval),
                value=val,
                reason_code=ReasonCode.OUT_OF_BOUNDS,
            )


def _validate_semantic_chat(payload: dict) -> None:
    """Validate semantic chat-message length."""

    msg = payload.get("message", "")

    length = len(str(msg))

    if length > 1024:
        raise _err(
            "$.message",
            "exceeds 1024 chars",
            expected="<=1024",
            got=str(length),
            reason_code=ReasonCode.INVALID_LENGTH,
        )


def _validate_semantic_wallet(payload: dict) -> None:
    """Validate semantic wallet amounts."""

    content = payload.get("content", [])

    if not isinstance(content, list):
        return

    for i, item in enumerate(content):
        if not isinstance(item, dict):
            continue

        amt = item.get("amount", 0)

        try:
            amt_int = int(amt)

        except (ValueError, TypeError):
            continue

        if amt_int < 0:
            raise _err(
                f"$.content[{i}].amount",
                "negative wallet amount",
                expected=">=0",
                got=str(amt),
                value=amt,
                reason_code=ReasonCode.OUT_OF_BOUNDS,
            )


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
    "MessageEvent": _validate_message_event,
    "Error": _validate_error,
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
    "SessionMetadata": _validate_session_metadata,
}


def validate_server_message(
    data: Any,
    strict: bool = False,
    strict_semantic: bool = False,
    **kwargs: Any,
) -> dict:
    """
    Validate an inbound Highrise server message.

    Parameters
    ----------
    data
        Decoded payload. Must be a ``dict`` carrying a ``_type`` key.
    strict
        When ``True``, semantic validation is also enforced. This is a
        promotion of ``strict_semantic``: the two flags are OR-ed so
        callers can turn on "everything" with a single switch. Kept as
        a separate name so future strict-only checks can be added here
        without overloading ``strict_semantic``.
    strict_semantic
        When ``True``, run the semantic layer on top of the structural
        layer: map bounds, chat length, wallet amount sign.
    **kwargs
        Ignored. Accepted for forward-compatibility so callers can pass
        new options without crashing older installs. New options must
        be given an explicit parameter above to take effect.

    Returns
    -------
    dict
        The validated payload (same object that was passed in).

    Raises
    ------
    HighriseFastValidationError
        Fail-fast: **exactly one** ``ValidationErrorDetail`` per raise.
        Multi-error collection is ``debug_payload``'s contract, not this
        function's.
    """
    if strict:
        strict_semantic = True

    if not isinstance(data, dict):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$",
                    "payload must be an object (dict)",
                    expected="dict",
                    got=_got_name(data),
                    value=data,
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ],
            payload=data,
        )

    if "_type" not in data:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$._type",
                    "missing required _type field",
                    expected="str",
                    got="missing",
                    reason_code=ReasonCode.MISSING_FIELD,
                )
            ],
            payload=data,
        )

    message_type = data["_type"]

    if not isinstance(message_type, str):
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$._type",
                    "must be a known string event type",
                    expected="str",
                    got=_got_name(message_type),
                    value=message_type,
                    reason_code=ReasonCode.WRONG_TYPE,
                )
            ],
            payload=data,
        )

    handler = _DISPATCH.get(message_type)

    if handler is None:
        raise HighriseFastValidationError(
            [
                ValidationErrorDetail(
                    "$._type",
                    f"unknown _type {_short_value(message_type)}",
                    expected="known event/response type",
                    got=_got_name(message_type),
                    value=message_type,
                    reason_code=ReasonCode.UNKNOWN_TYPE,
                )
            ],
            payload=data,
        )

    try:
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

    except HighriseFastValidationError as exc:
        if exc.payload is None:
            exc.payload = data

        raise

    return data


def _debug_tokens(path: str) -> list[str | int]:
    """

    Convert '$.user.id' or '$.content[0].amount'

    into ['user', 'id'] or ['content', 0, 'amount'].

    """

    tokens: list[str | int] = []

    i = 0

    if path.startswith("$"):
        i = 1

    while i < len(path):
        if path[i] == ".":
            j = i + 1

            while j < len(path) and path[j] not in ".[":
                j += 1

            tokens.append(path[i + 1 : j])

            i = j

        elif path[i] == "[":
            j = path.index("]", i)

            tokens.append(int(path[i + 1 : j]))

            i = j + 1

        else:
            i += 1

    return tokens


def _debug_get_value(payload: Any, path: str) -> Any:
    """
    Return the current value at ``path``, or ``None`` if it doesn't exist.

    Mirrors the traversal logic of ``_debug_set_value`` so both agree on
    what "the value at path X" means.
    """
    tokens = _debug_tokens(path)
    cur = payload
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(cur, list) or token >= len(cur):
                return None
            cur = cur[token]
        else:
            if not isinstance(cur, dict) or token not in cur:
                return None
            cur = cur[token]
    return cur


def _debug_default_for(
    expected: str, path: str, message: str, current_value: Any = None
) -> Any:
    """
    Choose a safe replacement value so validation can continue
    and discover the next error.

    Prefers the type named in ``expected`` when it exists. Falls back to
    inferring a type from ``current_value`` when ``expected`` holds a
    semantic constraint (e.g. "[-2000.0, 2000.0]", ">=0", "<=1024")
    instead of a Python type name.
    """
    e = (expected or "").lower()
    m = (message or "").lower()
    p = path.lower()

    if "str" in e:
        return "debug"

    if "int" in e:
        return 0

    if "float" in e:
        return 0.0

    if "bool" in e:
        return False

    if "dict" in e:
        return {}

    if "list" in e:
        return []

    if "literal" in e or "one of" in m:
        if "facing" in p:
            return "FrontRight"
        if "reaction" in p:
            return "heart"
        if "moderationtype" in p:
            return "mute"
        if "users[" in p and "][1]" in p:
            return "voice"
        return "debug"

    if current_value is not None:
        if isinstance(current_value, bool):
            return False
        if isinstance(current_value, float):
            return 0.0
        if isinstance(current_value, int):
            return 0
        if isinstance(current_value, str):
            return "debug"

    return "debug"


def _debug_set_value(payload: Any, path: str, value: Any) -> bool:
    """

    Repair one invalid field inside a copied payload so validation

    can continue and find more errors.

    """

    tokens = _debug_tokens(path)

    if not tokens:
        return False

    if tokens[0] == "_type":
        return False

    cur = payload

    for i, token in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]

        if isinstance(token, int):
            if not isinstance(cur, list):
                return False

            while len(cur) <= token:
                cur.append({} if isinstance(nxt, str) else [])

            cur = cur[token]

        else:
            if not isinstance(cur, dict):
                return False

            if token not in cur or not isinstance(cur[token], (dict, list)):
                cur[token] = {} if isinstance(nxt, str) else []

            cur = cur[token]

    last = tokens[-1]

    if isinstance(last, int):
        if not isinstance(cur, list):
            return False

        while len(cur) <= last:
            cur.append(None)

        cur[last] = value

    else:
        if not isinstance(cur, dict):
            return False

        cur[last] = value

    return True


def debug_payload(
    payload: Any,
    *,
    max_issues: int = 25,
    strict_semantic: bool = False,
) -> dict[str, Any]:
    """

    Debug-first validation report.

    This does NOT replace the fast runtime validator.

    It is meant for development, support, logs, dashboards, and bug reports.

    It tries to collect multiple problems instead of stopping at the first one.

    Set ``strict_semantic=True`` to also report semantic issues (map
    bounds, chat length, wallet sign); the default matches the runtime
    validator's default behavior.

    """

    issues: list[ValidationErrorDetail] = []

    seen: set[tuple[str, str, str]] = set()

    working = copy.deepcopy(payload)

    for _ in range(max_issues):
        try:
            validate_server_message(
                working,
                strict_semantic=strict_semantic,
            )

            break

        except HighriseFastValidationError as exc:
            if not exc.errors:
                break

            err = exc.errors[0]

            uid = (err.path, err.reason_code, err.message)

            if uid in seen:
                break

            seen.add(uid)

            issues.append(err)

            if (
                err.path == "$"
                or err.path == "$._type"
                or err.reason_code == ReasonCode.UNKNOWN_TYPE
            ):
                break

            current_value = _debug_get_value(working, err.path)
            default = _debug_default_for(
                err.expected, err.path, err.message, current_value
            )

            if not _debug_set_value(working, err.path, default):
                break

    return {
        "ok": len(issues) == 0,
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
        "first_error": issues[0].render() if issues else None,
        "payload": payload,
    }


def explain_debug(payload: Any, **kwargs: Any) -> str:
    """

    Human-readable multi-error explanation.

    """

    report = debug_payload(payload, **kwargs)

    if isinstance(payload, dict):
        type_name = payload.get("_type", "?")

    else:
        type_name = type(payload).__name__

    if report["ok"]:
        return f"{type_name}: OK"

    lines = [
        f"{type_name}: REJECTED ({report['issue_count']} issue(s))",
        "",
    ]

    for i, issue in enumerate(report["issues"], 1):
        expected = issue.get("expected") or "?"

        got = issue.get("got") or "?"

        lines.append(
            f"  {i}. [{issue.get('reason_code', '?')}] "
            f"{issue.get('path', '?')}: {issue.get('message', '?')} "
            f"(expected {expected}, got {got})"
        )

    return "\n".join(lines)


try:
    if "debug_payload" not in __all__:
        __all__.append("debug_payload")

    if "explain_debug" not in __all__:
        __all__.append("explain_debug")

except NameError:
    pass


BASE_PAYLOADS = {
    "SessionMetadata": {
        "_type": "SessionMetadata",
        "user_id": "u1",
        "room_info": {"owner_id": "u1", "room_name": "test"},
        "rate_limits": {},
        "connection_id": "1",
        "sdk_version": "1.0.0",
    },
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
            ]
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



def _hrf_clean_trailing_space_artifacts(value: Any) -> Any:
    """Remove accidental trailing-space artifacts from sample payloads."""
    if isinstance(value, dict):
        return {
            str(key).strip(): _hrf_clean_trailing_space_artifacts(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_hrf_clean_trailing_space_artifacts(item) for item in value]

    if isinstance(value, str):
        return value.strip()

    return value


_DISPATCH = {str(key).strip(): handler for key, handler in _DISPATCH.items()}

BASE_PAYLOADS = {
    str(key).strip(): _hrf_clean_trailing_space_artifacts(payload)
    for key, payload in BASE_PAYLOADS.items()
}
