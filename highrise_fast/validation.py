"""
highrise_fast/validation.py
────────────────────────────────────────────────────────────────────────────────
Official-compatible native validator for Highrise WebSocket server messages.

Replicates cattrs + attrs structuring semantics from the official
pocketzworld/python-bot-sdk *exactly*, while providing:

  • Multi-error collection  – every invalid field is reported in one pass
  • Rich JSON-path context  – e.g.  $.users[1][0].username
  • Expected / actual types  – e.g.  expected str, got int
  • Value snippets           – truncated repr of the offending value
  • Zero external deps       – pure Python, no cattrs / attrs needed

Key cattrs behaviours replicated
─────────────────────────────────
  str   → isinstance(v, str)
  int   → isinstance(v, int) and not isinstance(v, bool)
  float → isinstance(v, (int, float)) and not isinstance(v, bool)
  bool  → isinstance(v, bool)
  list  → ANY iterable (str, dict, list, tuple …); empty iterables → []
  dict  → isinstance(v, dict)
  Literal → value must be in the allowed set
  Optional (T | None) → None accepted
  Default (T = x)     → key may be absent; None still rejected unless T | None
  Extra keys          → silently ignored (same as attrs)
"""
from __future__ import annotations
import json as _json
from typing import Any, Callable, Sequence

__all__ = ["HighriseFastValidationError", "ValidationErrorDetail", "validate_server_message"]

_MAX_SNIPPET = 60
_MAX_LIST_ITEMS = 10_000


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

class ValidationErrorDetail:
    """One atomic validation failure with full context."""
    __slots__ = ("path", "message", "expected", "got", "value")

    def __init__(self, path, message, expected="", got="", value=None):
        self.path = path
        self.message = message
        self.expected = expected
        self.got = got
        self.value = value

    def render(self):
        parts = [f"  x {self.path}: {self.message}"]
        if self.expected:
            parts.append(f"expected {self.expected}")
        if self.got:
            parts.append(f"got {self.got}")
        s = repr(self.value)
        if len(s) > _MAX_SNIPPET:
            s = s[:_MAX_SNIPPET] + "..."
        parts.append(f"value={s}")
        return " | ".join(parts)

    def __repr__(self):
        return f"<ValidationError {self.path}: {self.message}>"


class HighriseFastValidationError(ValueError):
    """
    Raised when a server message fails native validation.

    Attributes
    ----------
    errors : list[ValidationErrorDetail]
        Every individual failure found in the payload (single-pass).
    payload : Any
        The original payload that was validated (useful for logging).
    """
    def __init__(self, errors, payload=None):
        if isinstance(errors, str):
            errors = [ValidationErrorDetail("$", errors)]
        self.errors = errors
        self.payload = payload
        super().__init__(self.render())

    def render(self):
        n = len(self.errors)
        lines = [f"highrise_fast validation failed ({n} error{'s' if n != 1 else ''})"]
        for e in self.errors:
            lines.append(e.render())
        if self.payload is not None:
            try:
                p = _json.dumps(self.payload, default=str, ensure_ascii=False)
                if len(p) > 200:
                    p = p[:200] + "..."
                lines.append(f"  payload: {p}")
            except Exception:
                pass
        return "\n".join(lines)

    def __str__(self):
        return self.render()


class _Ctx:
    """Lightweight error accumulator passed through every validator."""
    __slots__ = ("errors",)

    def __init__(self):
        self.errors = []

    def add(self, path, msg, exp="", got="", val=None):
        self.errors.append(ValidationErrorDetail(path, msg, exp, got, val))

    def raise_if_any(self, payload=None):
        if self.errors:
            raise HighriseFastValidationError(self.errors, payload)


def _tn(v):
    """Human-readable type name."""
    return type(v).__name__


# ═══════════════════════════════════════════════════════════════════════════════
# PRIMITIVE TYPE CHECKERS
# ═══════════════════════════════════════════════════════════════════════════════

def _ok_str(v, path, ctx):
    if isinstance(v, str):
        return True
    ctx.add(path, "must be a string", "str", _tn(v), v)
    return False

def _ok_int(v, path, ctx):
    # cattrs JSON preconf: bool is NOT int
    if isinstance(v, int) and not isinstance(v, bool):
        return True
    ctx.add(path, "must be an integer", "int", _tn(v), v)
    return False

def _ok_float(v, path, ctx):
    # cattrs: int is silently promoted to float; bool is NOT numeric
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    ctx.add(path, "must be a number", "float", _tn(v), v)
    return False

def _ok_bool(v, path, ctx):
    if isinstance(v, bool):
        return True
    ctx.add(path, "must be a boolean", "bool", _tn(v), v)
    return False

def _ok_literal(v, path, allowed, ctx):
    if isinstance(v, str) and v in allowed:
        return True
    ctx.add(path, f"must be one of {list(allowed)}", "Literal", repr(v), v)
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# FIELD-LEVEL HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

_MISSING = object()

def _field(d, key, path, check, ctx, required=True, nullable=False):
    """
    Validate d[key] with *check*.

    required : If True and key absent → error.
    nullable : If True and value is None → accepted (T | None).
    """
    val = d.get(key, _MISSING)
    if val is _MISSING:
        if required:
            ctx.add(f"{path}.{key}", "missing required key", "present", "absent")
        return
    if val is None:
        if nullable:
            return
        ctx.add(f"{path}.{key}", "must not be null", "non-null", "NoneType", None)
        return
    check(val, f"{path}.{key}", ctx)

def _str(d, k, p, ctx, **kw):
    _field(d, k, p, _ok_str, ctx, **kw)

def _int(d, k, p, ctx, **kw):
    _field(d, k, p, _ok_int, ctx, **kw)

def _float(d, k, p, ctx, **kw):
    _field(d, k, p, _ok_float, ctx, **kw)

def _bool(d, k, p, ctx, **kw):
    _field(d, k, p, _ok_bool, ctx, **kw)

def _literal(d, k, p, allowed, ctx, **kw):
    _field(d, k, p, lambda v, pp, c: _ok_literal(v, pp, allowed, c), ctx, **kw)


# ═══════════════════════════════════════════════════════════════════════════════
# ITERABLE / LIST HELPER  (cattrs accepts ANY iterable for list[T])
# ═══════════════════════════════════════════════════════════════════════════════

def _iter_list(val, path, elem_check, ctx):
    """
    Validate val as list[T].  cattrs iterates with iter(val) so ANY iterable
    is accepted (including "" and {}).  Non-iterables are rejected.
    """
    try:
        it = iter(val)
    except TypeError:
        ctx.add(path, "must be iterable", "iterable", _tn(val), val)
        return
    for i, item in enumerate(it):
        if i >= _MAX_LIST_ITEMS:
            ctx.add(path, "iterable too large", f"<={_MAX_LIST_ITEMS}", "too many")
            break
        elem_check(item, f"{path}[{i}]", ctx)

def _list_field(d, key, path, elem_check, ctx, required=True):
    val = d.get(key, _MISSING)
    if val is _MISSING:
        if required:
            ctx.add(f"{path}.{key}", "missing required key", "present", "absent")
        return
    if val is None:
        ctx.add(f"{path}.{key}", "must not be null", "iterable", "NoneType", None)
        return
    _iter_list(val, f"{path}.{key}", elem_check, ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# TUPLE HELPER  (for list[tuple[A, B]] fields)
# ═══════════════════════════════════════════════════════════════════════════════

def _tuple_elem(val, path, checks, ctx):
    """Validate one tuple element (represented as a JSON array)."""
    try:
        items = list(iter(val))
    except TypeError:
        ctx.add(path, "must be iterable (tuple)", "iterable", _tn(val), val)
        return
    if len(items) != len(checks):
        ctx.add(path, f"tuple length must be {len(checks)}", str(len(checks)), str(len(items)), val)
        return
    for idx, (item, check) in enumerate(zip(items, checks)):
        check(item, f"{path}[{idx}]", ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCT (DICT) VALIDATORS
# ═══════════════════════════════════════════════════════════════════════════════

def _v_user(v, path, ctx):
    """User { id: str, username: str }"""
    if not isinstance(v, dict):
        ctx.add(path, "must be a User object", "dict", _tn(v), v)
        return
    _str(v, "id", path, ctx)
    _str(v, "username", path, ctx)

_FACINGS = ("FrontRight", "FrontLeft", "BackRight", "BackLeft")

def _v_position(v, path, ctx):
    """Position { x: float, y: float, z: float, facing: Facing = "FrontRight" }"""
    if not isinstance(v, dict):
        ctx.add(path, "must be a Position object", "dict", _tn(v), v)
        return
    _float(v, "x", path, ctx)
    _float(v, "y", path, ctx)
    _float(v, "z", path, ctx)
    # facing is optional (has default "FrontRight")
    _literal(v, "facing", path, _FACINGS, ctx, required=False)

def _v_anchor_position(v, path, ctx):
    """AnchorPosition { entity_id: str, anchor_ix: int }"""
    if not isinstance(v, dict):
        ctx.add(path, "must be an AnchorPosition object", "dict", _tn(v), v)
        return
    _str(v, "entity_id", path, ctx)
    _int(v, "anchor_ix", path, ctx)

def _v_position_union(v, path, ctx):
    """Position | AnchorPosition – discriminated by keys."""
    if not isinstance(v, dict):
        ctx.add(path, "must be Position or AnchorPosition", "dict", _tn(v), v)
        return
    if "entity_id" in v or "anchor_ix" in v:
        _v_anchor_position(v, path, ctx)
    else:
        _v_position(v, path, ctx)

def _v_currency_item(v, path, ctx):
    """CurrencyItem { type: str, amount: int }"""
    if not isinstance(v, dict):
        ctx.add(path, "must be a CurrencyItem object", "dict", _tn(v), v)
        return
    _str(v, "type", path, ctx)
    _int(v, "amount", path, ctx)

def _v_item(v, path, ctx):
    """Item { type: "clothing", amount: int, id: str, ... }"""
    if not isinstance(v, dict):
        ctx.add(path, "must be an Item object", "dict", _tn(v), v)
        return
    _literal(v, "type", path, ("clothing",), ctx)
    _int(v, "amount", path, ctx)
    _str(v, "id", path, ctx)
    _bool(v, "account_bound", path, ctx, required=False)
    _int(v, "active_palette", path, ctx, required=False, nullable=True)

def _v_tip_item(v, path, ctx):
    """Item | CurrencyItem – try Item first (requires type="clothing" + id)."""
    if not isinstance(v, dict):
        ctx.add(path, "must be Item or CurrencyItem", "dict", _tn(v), v)
        return
    if v.get("type") == "clothing" and "id" in v:
        _v_item(v, path, ctx)
    else:
        _v_currency_item(v, path, ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# EVENT / RESPONSE VALIDATORS
# ═══════════════════════════════════════════════════════════════════════════════

def _e_chat(p, ctx):
    """ChatEvent { user: User, message: str, whisper: bool }"""
    _field(p, "user", "$", _v_user, ctx)
    _str(p, "message", "$", ctx)
    _bool(p, "whisper", "$", ctx)

def _e_user_joined(p, ctx):
    """UserJoinedEvent { user: User, position: Position|AnchorPosition }"""
    _field(p, "user", "$", _v_user, ctx)
    _field(p, "position", "$", _v_position_union, ctx)

def _e_user_left(p, ctx):
    """UserLeftEvent { user: User }"""
    _field(p, "user", "$", _v_user, ctx)

def _e_user_moved(p, ctx):
    """UserMovedEvent { user: User, position: Position|AnchorPosition }"""
    _field(p, "user", "$", _v_user, ctx)
    _field(p, "position", "$", _v_position_union, ctx)

def _e_emote(p, ctx):
    """EmoteEvent { user: User, emote_id: str, receiver: User|None = None }"""
    _field(p, "user", "$", _v_user, ctx)
    _str(p, "emote_id", "$", ctx)
    _field(p, "receiver", "$", _v_user, ctx, required=False, nullable=True)

_REACTIONS = ("clap", "heart", "thumbs", "wave", "wink")

def _e_reaction(p, ctx):
    """ReactionEvent { user: User, reaction: Reaction, receiver: User }"""
    _field(p, "user", "$", _v_user, ctx)
    _literal(p, "reaction", "$", _REACTIONS, ctx)
    _field(p, "receiver", "$", _v_user, ctx)

def _e_tip(p, ctx):
    """TipReactionEvent { sender: User, receiver: User, item: Item|CurrencyItem }"""
    _field(p, "sender", "$", _v_user, ctx)
    _field(p, "receiver", "$", _v_user, ctx)
    _field(p, "item", "$", _v_tip_item, ctx)

def _voice_tuple(v, path, ctx):
    _tuple_elem(v, path, (
        _v_user,
        lambda val, pp, c: _ok_literal(val, pp, ("voice", "muted"), c),
    ), ctx)

def _e_voice(p, ctx):
    """VoiceEvent { users: list[(User, "voice"|"muted")], seconds_left: int }"""
    _list_field(p, "users", "$", _voice_tuple, ctx)
    _int(p, "seconds_left", "$", ctx)

def _e_channel(p, ctx):
    """ChannelEvent { sender_id: str, msg: str, tags: list[str] = [] }"""
    _str(p, "sender_id", "$", ctx)
    _str(p, "msg", "$", ctx)
    _list_field(p, "tags", "$", lambda v, pp, c: _ok_str(v, pp, c), ctx, required=False)

_MOD_TYPES = ("kick", "mute", "unmute", "ban", "unban")

def _e_moderated(p, ctx):
    """RoomModeratedEvent { moderatorId: str, targetUserId: str,
    moderationType: Literal[...], duration: int|None }"""
    _str(p, "moderatorId", "$", ctx)
    _str(p, "targetUserId", "$", ctx)
    _literal(p, "moderationType", "$", _MOD_TYPES, ctx)
    # duration: required but nullable (int | None, no default)
    _int(p, "duration", "$", ctx, nullable=True)

def _e_error(p, ctx):
    """Error { message: str, do_not_reconnect: bool = False, rid: str|None = None }"""
    _str(p, "message", "$", ctx)
    _bool(p, "do_not_reconnect", "$", ctx, required=False)
    _str(p, "rid", "$", ctx, required=False, nullable=True)

def _e_message(p, ctx):
    """MessageEvent { user_id: str, conversation_id: str, is_new_conversation: bool }"""
    _str(p, "user_id", "$", ctx)
    _str(p, "conversation_id", "$", ctx)
    _bool(p, "is_new_conversation", "$", ctx)

def _r_wallet(p, ctx):
    """GetWalletResponse { content: list[CurrencyItem], rid: str }"""
    _list_field(p, "content", "$", _v_currency_item, ctx)
    _str(p, "rid", "$", ctx)

def _room_user_tuple(v, path, ctx):
    _tuple_elem(v, path, (_v_user, _v_position_union), ctx)

def _r_room_users(p, ctx):
    """GetRoomUsersResponse { content: list[(User, Position|AnchorPosition)], rid: str }"""
    _list_field(p, "content", "$", _room_user_tuple, ctx)
    _str(p, "rid", "$", ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# DISPATCH TABLE
# ═══════════════════════════════════════════════════════════════════════════════

_DISPATCH = {
    # events
    "ChatEvent":           _e_chat,
    "UserJoinedEvent":     _e_user_joined,
    "UserLeftEvent":       _e_user_left,
    "UserMovedEvent":      _e_user_moved,
    "EmoteEvent":          _e_emote,
    "ReactionEvent":       _e_reaction,
    "TipReactionEvent":    _e_tip,
    "VoiceEvent":          _e_voice,
    "ChannelEvent":        _e_channel,
    "RoomModeratedEvent":  _e_moderated,
    "MessageEvent":        _e_message,
    "Error":               _e_error,
    # responses
    "GetWalletResponse":    _r_wallet,
    "GetRoomUsersResponse": _r_room_users,
}

_KNOWN_TYPES = tuple(_DISPATCH)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def validate_server_message(data, **kwargs):
    """
    Validate a decoded server message (already json.loads-ed).

    Returns *data* unchanged on success.
    Raises HighriseFastValidationError with ALL detected problems on failure.

    Usage::

        try:
            validate_server_message(payload)
        except HighriseFastValidationError as exc:
            log.error("Bad payload:\\n%s", exc)
    """
    if not isinstance(data, dict):
        raise HighriseFastValidationError(
            f"payload must be a JSON object, got {_tn(data)}", payload=data)

    ctx = _Ctx()

    t = data.get("_type", _MISSING)
    if t is _MISSING:
        ctx.add("$._type", "missing required key", "present", "absent")
        ctx.raise_if_any(data)
    if not isinstance(t, str):
        ctx.add("$._type", "must be a string", "str", _tn(t), t)
        ctx.raise_if_any(data)

    handler = _DISPATCH.get(t)
    if handler is None:
        ctx.add("$._type", "unknown event/response type",
                f"one of {list(_KNOWN_TYPES)}", repr(t), t)
        ctx.raise_if_any(data)

    handler(data, ctx)
    ctx.raise_if_any(data)
    return data