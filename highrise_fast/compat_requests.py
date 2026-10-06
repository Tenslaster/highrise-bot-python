"""Compatibility shims for official request classes.

This module dynamically generates lightweight request classes that mirror the
official request objects. Each generated class:

* accepts positional arguments in field order;
* accepts keyword arguments by field name;
* applies default values for missing fields;
* exposes the matching response class as ``Response``.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from .models import (
    AnchorHitResponse,
    BuyItemResponse,
    BuyRoomBoostResponse,
    BuyVoiceTimeResponse,
    ChangeBackpackResponse,
    ChangeRoomPrivilegeResponse,
    ChannelResponse,
    ChatResponse,
    CheckVoiceChatResponse,
    EmoteResponse,
    FloorHitResponse,
    GetBackpackResponse,
    GetConversationsResponse,
    GetInventoryResponse,
    GetMessagesResponse,
    GetRoomPrivilegeResponse,
    GetRoomUsersResponse,
    GetUserOutfitResponse,
    GetWalletResponse,
    IndicatorResponse,
    InviteSpeakerResponse,
    KeepaliveResponse,
    LeaveConversationResponse,
    MessageMediaResponse,
    ModerateRoomResponse,
    MoveUserToRoomResponse,
    ReactionResponse,
    RemoveSpeakerResponse,
    SendBulkMessageResponse,
    SendMessageResponse,
    SetOutfitResponse,
    TeleportResponse,
    TipUserResponse,
)

__all__: list[str] = []

logger = logging.getLogger("highrise_fast.compat_requests")


class _Request:
    """Minimal runtime-compatible request object.

    Subclasses declare ``_fields`` and optional ``_defaults``. The
    constructor maps positional arguments to ``_fields`` in order and
    keyword arguments by field name.
    """

    _fields: ClassVar[tuple[str, ...]] = ()
    _defaults: ClassVar[dict[str, Any]] = {}
    Response: ClassVar[type[Any] | None] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the request.

        Extra positional args beyond ``_fields`` and unknown kwargs are
        logged at debug level and ignored (compat-shim leniency).
        """
        if len(args) > len(self._fields):
            logger.debug(
                "%s: %d positional args provided for %d fields; extras ignored",
                type(self).__name__,
                len(args),
                len(self._fields),
            )

        values: dict[str, Any] = dict(zip(self._fields, args))
        unknown = set(kwargs) - set(self._fields)
        if unknown:
            logger.debug(
                "%s: unknown kwarg(s) ignored: %s",
                type(self).__name__,
                ", ".join(sorted(unknown)),
            )
        values.update(kwargs)

        for name in self._fields:
            if name in values:
                value = values[name]
            else:
                value = self._defaults.get(name)
                if callable(value):
                    value = value()
            setattr(self, name, value)

    def __repr__(self) -> str:
        """Return a developer-friendly string representation."""
        parts = [f"{name}={getattr(self, name, None)!r}" for name in self._fields]
        return f"{type(self).__name__}({', '.join(parts)})"


_REQUESTS: tuple[tuple[str, tuple[str, ...], type[Any]], ...] = (
    (
        "ChatRequest",
        ("message", "whisper_target_id", "rid"),
        ChatResponse,
    ),
    (
        "IndicatorRequest",
        ("icon", "rid"),
        IndicatorResponse,
    ),
    (
        "ReactionRequest",
        ("reaction", "target_user_id", "rid"),
        ReactionResponse,
    ),
    (
        "EmoteRequest",
        ("emote_id", "target_user_id", "rid"),
        EmoteResponse,
    ),
    (
        "ChannelRequest",
        ("message", "tags", "only_to", "rid"),
        ChannelResponse,
    ),
    (
        "FloorHitRequest",
        ("destination", "rid"),
        FloorHitResponse,
    ),
    (
        "TeleportRequest",
        ("user_id", "destination", "rid"),
        TeleportResponse,
    ),
    (
        "GetRoomUsersRequest",
        ("rid",),
        GetRoomUsersResponse,
    ),
    (
        "GetWalletRequest",
        ("rid",),
        GetWalletResponse,
    ),
    (
        "GetRoomPrivilegeRequest",
        ("user_id", "rid"),
        GetRoomPrivilegeResponse,
    ),
    (
        "ChangeRoomPrivilegeRequest",
        ("user_id", "permissions", "rid"),
        ChangeRoomPrivilegeResponse,
    ),
    (
        "ModerateRoomRequest",
        ("user_id", "moderation_action", "action_length", "rid"),
        ModerateRoomResponse,
    ),
    (
        "KeepaliveRequest",
        ("rid",),
        KeepaliveResponse,
    ),
    (
        "MoveUserToRoomRequest",
        ("user_id", "room_id", "rid"),
        MoveUserToRoomResponse,
    ),
    (
        "AnchorHitRequest",
        ("anchor", "rid"),
        AnchorHitResponse,
    ),
    (
        "CheckVoiceChatRequest",
        ("rid",),
        CheckVoiceChatResponse,
    ),
    (
        "InviteSpeakerRequest",
        ("user_id", "rid"),
        InviteSpeakerResponse,
    ),
    (
        "RemoveSpeakerRequest",
        ("user_id", "rid"),
        RemoveSpeakerResponse,
    ),
    (
        "GetUserOutfitRequest",
        ("user_id", "rid"),
        GetUserOutfitResponse,
    ),
    (
        "GetBackpackRequest",
        ("user_id", "rid"),
        GetBackpackResponse,
    ),
    (
        "ChangeBackpackRequest",
        ("user_id", "changes", "rid"),
        ChangeBackpackResponse,
    ),
    (
        "GetConversationsRequest",
        ("not_joined", "last_id", "rid"),
        GetConversationsResponse,
    ),
    (
        "SendMessageRequest",
        (
            "conversation_id",
            "content",
            "type",
            "room_id",
            "world_id",
            "media_id",
            "rid",
        ),
        SendMessageResponse,
    ),
    (
        "GetMessagesRequest",
        ("conversation_id", "last_message_id", "rid"),
        GetMessagesResponse,
    ),
    (
        "LeaveConversationRequest",
        ("conversation_id", "rid"),
        LeaveConversationResponse,
    ),
    (
        "BuyVoiceTimeRequest",
        ("payment_method", "rid"),
        BuyVoiceTimeResponse,
    ),
    (
        "BuyRoomBoostRequest",
        ("payment_method", "amount", "rid"),
        BuyRoomBoostResponse,
    ),
    (
        "TipUserRequest",
        ("user_id", "gold_bar", "rid"),
        TipUserResponse,
    ),
    (
        "SetOutfitRequest",
        ("outfit", "rid"),
        SetOutfitResponse,
    ),
    (
        "GetInventoryRequest",
        ("rid",),
        GetInventoryResponse,
    ),
    (
        "BuyItemRequest",
        ("item_id", "rid"),
        BuyItemResponse,
    ),
    (
        "SendBulkMessageRequest",
        ("user_ids", "content", "type", "room_id", "world_id", "rid"),
        SendBulkMessageResponse,
    ),
    (
        "MessageMediaRequest",
        ("media", "rid"),
        MessageMediaResponse,
    ),
)

_DEFAULTS: dict[str, dict[str, Any]] = {
    "ChannelRequest": {"tags": set},
    "GetConversationsRequest": {"not_joined": False},
    "BuyRoomBoostRequest": {"amount": 1},
}

for _name, _fields, _response_cls in _REQUESTS:
    _cls = type(
        _name,
        (_Request,),
        {
            "__module__": __name__,
            "__qualname__": _name,
            "__doc__": f"Compatibility shim for official {_name}.",
            "_fields": _fields,
            "_defaults": _DEFAULTS.get(_name, {}),
            "Response": _response_cls,
            _response_cls.__name__: _response_cls,
        },
    )

    globals()[_name] = _cls
    __all__.append(_name)