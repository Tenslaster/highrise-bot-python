"""
highrise_fast.compat_requests — compatibility shim for official *Request classes.

This module exists so code written against the official SDK can do things like:

    from highrise_fast.models import ChatRequest, GetRoomUsersRequest

and use:

    GetRoomUsersRequest.Response
    GetRoomUsersRequest.GetRoomUsersResponse

These request classes are not used by highrise_fast's wire layer. They are
provided for import compatibility and lightweight object construction.
"""

from typing import Any, ClassVar

from . import (
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


class _Request:
    """Minimal runtime-compatible request object."""

    _fields: tuple[str, ...] = ()
    Response: ClassVar[Any] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        values = dict(zip(self._fields, args))
        values.update(kwargs)

        for name in self._fields:
            setattr(self, name, values.get(name))

    def __repr__(self) -> str:
        parts = [f"{name}={getattr(self, name, None)!r}" for name in self._fields]
        return f"{type(self).__name__}({', '.join(parts)})"


_REQUESTS: tuple[tuple[str, tuple[str, ...], Any], ...] = (
    ("ChatRequest", ("message", "whisper_target_id", "rid"), ChatResponse),
    ("IndicatorRequest", ("icon", "rid"), IndicatorResponse),
    ("ReactionRequest", ("reaction", "target_user_id", "rid"), ReactionResponse),
    ("EmoteRequest", ("emote_id", "target_user_id", "rid"), EmoteResponse),
    ("ChannelRequest", ("message", "tags", "only_to", "rid"), ChannelResponse),
    ("FloorHitRequest", ("destination", "rid"), FloorHitResponse),
    ("TeleportRequest", ("user_id", "destination", "rid"), TeleportResponse),
    ("GetRoomUsersRequest", ("rid",), GetRoomUsersResponse),
    ("GetWalletRequest", ("rid",), GetWalletResponse),
    ("GetRoomPrivilegeRequest", ("user_id", "rid"), GetRoomPrivilegeResponse),
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
    ("KeepaliveRequest", ("rid",), KeepaliveResponse),
    ("MoveUserToRoomRequest", ("user_id", "room_id", "rid"), MoveUserToRoomResponse),
    ("AnchorHitRequest", ("anchor", "rid"), AnchorHitResponse),
    ("CheckVoiceChatRequest", ("rid",), CheckVoiceChatResponse),
    ("InviteSpeakerRequest", ("user_id", "rid"), InviteSpeakerResponse),
    ("RemoveSpeakerRequest", ("user_id", "rid"), RemoveSpeakerResponse),
    ("GetUserOutfitRequest", ("user_id", "rid"), GetUserOutfitResponse),
    ("GetBackpackRequest", ("user_id", "rid"), GetBackpackResponse),
    ("ChangeBackpackRequest", ("user_id", "changes", "rid"), ChangeBackpackResponse),
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
    ("LeaveConversationRequest", ("conversation_id", "rid"), LeaveConversationResponse),
    ("BuyVoiceTimeRequest", ("payment_method", "rid"), BuyVoiceTimeResponse),
    ("BuyRoomBoostRequest", ("payment_method", "amount", "rid"), BuyRoomBoostResponse),
    ("TipUserRequest", ("user_id", "gold_bar", "rid"), TipUserResponse),
    ("SetOutfitRequest", ("outfit", "rid"), SetOutfitResponse),
    ("GetInventoryRequest", ("rid",), GetInventoryResponse),
    ("BuyItemRequest", ("item_id", "rid"), BuyItemResponse),
    (
        "SendBulkMessageRequest",
        ("user_ids", "content", "type", "room_id", "world_id", "rid"),
        SendBulkMessageResponse,
    ),
    ("MessageMediaRequest", ("media", "rid"), MessageMediaResponse),
)


for _name, _fields, _response_cls in _REQUESTS:
    _cls = type(
        _name,
        (_Request,),
        {
            "_fields": _fields,
            "Response": _response_cls,
            _response_cls.__name__: _response_cls,
            "__module__": __name__,
            "__doc__": f"Compatibility shim for official {_name}.",
        },
    )

    globals()[_name] = _cls
    __all__.append(_name)
