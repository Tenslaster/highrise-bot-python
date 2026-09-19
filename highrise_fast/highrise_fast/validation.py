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

def _check_dict(data: dict, key: str, path: str) -> dict | None:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if val is None:
        return None
    if not isinstance(val, dict):
        raise HighriseFastValidationError(f"ClassValidationError: {path}.{key} must be dict, got {_type_name(val)}")
    return val

def _check_any(data: dict, key: str, path: str) -> Any:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    return data[key]

def _check_list_tuples(data: dict, key: str, path: str, expected_len: int) -> list:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if not isinstance(val, list):
        raise HighriseFastValidationError(f"ClassValidationError: {path}.{key} must be list, got {_type_name(val)}")
    
    for i, row in enumerate(val):
        if not isinstance(row, (list, tuple)):
            raise HighriseFastValidationError(f"ClassValidationError: {path}.{key}[{i}] must be tuple, got {_type_name(row)}")
        if len(row) != expected_len:
            raise HighriseFastValidationError(f"ClassValidationError: {path}.{key}[{i}] length {len(row)} != {expected_len}")
        
        # First element of these tuples is always a User dict
        if not isinstance(row[0], dict):
            raise HighriseFastValidationError(f"ClassValidationError: {path}.{key}[{i}][0] must be dict, got {_type_name(row[0])}")
            
    return val

def _check_list_dicts(data: dict, key: str, path: str) -> list:
    if key not in data:
        raise HighriseFastValidationError(f"KeyError: '{key}' in {path}")
    val = data[key]
    if not isinstance(val, list):
        raise HighriseFastValidationError(f"ClassValidationError: {path}.{key} must be list, got {_type_name(val)}")
    for i, item in enumerate(val):
        if not isinstance(item, dict):
            raise HighriseFastValidationError(f"ClassValidationError: {path}.{key}[{i}] must be dict, got {_type_name(item)}")
    return val

def _validate_user(d: dict, path: str):
    _check_any(d, "id", path)
    _check_any(d, "username", path)

def _validate_position(d: dict, path: str):
    _check_any(d, "x", path)
    _check_any(d, "y", path)
    _check_any(d, "z", path)
    _check_any(d, "facing", path)

def _validate_currency_item(d: dict, path: str):
    _check_any(d, "type", path)
    _check_any(d, "amount", path)

# ─────────────────────────────────────────────────────────────
# MESSAGE VALIDATORS (Only checking required keys & structures)
# ─────────────────────────────────────────────────────────────
def _validate_chat_event(p: dict):
    u = _check_dict(p, "user", "$")
    if u is not None: _validate_user(u, "$.user")
    _check_any(p, "message", "$")

def _validate_user_joined(p: dict):
    u = _check_dict(p, "user", "$")
    if u is not None: _validate_user(u, "$.user")
    pos = _check_dict(p, "position", "$")
    if pos is not None: _validate_position(pos, "$.position")

def _validate_user_left(p: dict):
    u = _check_dict(p, "user", "$")
    if u is not None: _validate_user(u, "$.user")

def _validate_user_moved(p: dict):
    u = _check_dict(p, "user", "$")
    if u is not None: _validate_user(u, "$.user")
    pos = _check_dict(p, "position", "$")
    if pos is not None: _validate_position(pos, "$.position")

def _validate_emote(p: dict):
    u = _check_dict(p, "user", "$")
    if u is not None: _validate_user(u, "$.user")
    _check_any(p, "emote_id", "$")

def _validate_reaction(p: dict):
    u = _check_dict(p, "user", "$")
    if u is not None: _validate_user(u, "$.user")
    _check_any(p, "reaction", "$")

def _validate_tip(p: dict):
    s = _check_dict(p, "sender", "$")
    if s is not None: _validate_user(s, "$.sender")
    r = _check_dict(p, "receiver", "$")
    if r is not None: _validate_user(r, "$.receiver")
    i = _check_dict(p, "item", "$")
    if i is not None: _validate_currency_item(i, "$.item")

def _validate_voice(p: dict):
    _check_list_tuples(p, "users", "$", 2)
    for i, row in enumerate(p["users"]):
        if isinstance(row[0], dict):
            _validate_user(row[0], f"$.users[{i}][0]")
    _check_any(p, "seconds_left", "$")

def _validate_channel(p: dict):
    _check_any(p, "sender_id", "$")
    _check_any(p, "msg", "$")

def _validate_moderated(p: dict):
    _check_any(p, "moderatorId", "$")
    _check_any(p, "targetUserId", "$")
    _check_any(p, "moderationType", "$")
    _check_any(p, "duration", "$")

def _validate_error(p: dict):
    _check_any(p, "message", "$")

def _validate_wallet(p: dict):
    _check_list_dicts(p, "content", "$")
    for i, item in enumerate(p["content"]):
        _validate_currency_item(item, f"$.content[{i}]")
    _check_any(p, "rid", "$")

def _validate_room_users(p: dict):
    _check_list_tuples(p, "content", "$", 2)
    for i, row in enumerate(p["content"]):
        if isinstance(row[0], dict): _validate_user(row[0], f"$.content[{i}][0]")
        if isinstance(row[1], dict): _validate_position(row[1], f"$.content[{i}][1]")

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
        raise HighriseFastValidationError(f"payload must be an object, got {_type_name(data)}")
    
    if "_type" not in data:
        raise HighriseFastValidationError("KeyError: '_type'")
        
    t = data["_type"]
    handler = _DISPATCH.get(t)
    
    if handler is None:
        raise HighriseFastValidationError(f"ClassValidationError: unknown _type '{t}'")
        
    handler(data)
    return data