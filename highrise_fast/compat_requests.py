"""Typed Bot API request models with their response classes."""

from __future__ import annotations

from collections import Counter
from dataclasses import field, make_dataclass
from typing import Literal

from .models import (
    AnchorHitResponse,
    AnchorPosition,
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
    Item,
    KeepaliveResponse,
    LeaveConversationResponse,
    MessageMedia,
    MessageMediaResponse,
    ModerateRoomResponse,
    MoveUserToRoomResponse,
    Position,
    Reaction,
    ReactionResponse,
    RemoveSpeakerResponse,
    RoomPermissions,
    SendBulkMessageResponse,
    SendMessageResponse,
    SetOutfitResponse,
    TeleportResponse,
    TipUserResponse,
)

_TEXT = Literal["text", "invite"]
_PAYMENT = Literal["bot_wallet_only"]
_ACTION = Literal["kick", "ban", "unban", "mute"]
_USER_ID = ("user_id", str)
_ROOM_ID = ("room_id", str | None, None)
_WORLD_ID = ("world_id", str | None, None)
_DESTINATION = ("destination", Position)
_RID = ("rid", str | None, None)

_REQUESTS = (
    (
        "ChatRequest",
        ChatResponse,
        (
            ("message", str),
            ("whisper_target_id", str | None, None),
        ),
    ),
    ("IndicatorRequest", IndicatorResponse, (("icon", str | None, None),)),
    (
        "ReactionRequest",
        ReactionResponse,
        (
            ("reaction", Reaction),
            ("target_user_id", str),
        ),
    ),
    (
        "EmoteRequest",
        EmoteResponse,
        (
            ("emote_id", str),
            ("target_user_id", str | None, None),
        ),
    ),
    (
        "ChannelRequest",
        ChannelResponse,
        (
            ("message", str),
            ("tags", set[str], field(default_factory=set)),
            ("only_to", set[str] | None, None),
        ),
    ),
    ("FloorHitRequest", FloorHitResponse, (_DESTINATION,)),
    ("TeleportRequest", TeleportResponse, (_USER_ID, _DESTINATION)),
    ("GetRoomUsersRequest", GetRoomUsersResponse, ()),
    ("GetWalletRequest", GetWalletResponse, ()),
    ("GetRoomPrivilegeRequest", GetRoomPrivilegeResponse, (_USER_ID,)),
    (
        "ChangeRoomPrivilegeRequest",
        ChangeRoomPrivilegeResponse,
        (
            _USER_ID,
            ("permissions", RoomPermissions),
        ),
    ),
    (
        "ModerateRoomRequest",
        ModerateRoomResponse,
        (
            _USER_ID,
            ("moderation_action", _ACTION),
            ("action_length", int | None, None),
        ),
    ),
    ("KeepaliveRequest", KeepaliveResponse, ()),
    ("MoveUserToRoomRequest", MoveUserToRoomResponse, (_USER_ID, ("room_id", str))),
    ("AnchorHitRequest", AnchorHitResponse, (("anchor", AnchorPosition),)),
    ("CheckVoiceChatRequest", CheckVoiceChatResponse, ()),
    ("InviteSpeakerRequest", InviteSpeakerResponse, (_USER_ID,)),
    ("RemoveSpeakerRequest", RemoveSpeakerResponse, (_USER_ID,)),
    ("GetUserOutfitRequest", GetUserOutfitResponse, (_USER_ID,)),
    ("GetBackpackRequest", GetBackpackResponse, (_USER_ID,)),
    ("ChangeBackpackRequest", ChangeBackpackResponse, (_USER_ID, ("changes", Counter[str]))),
    (
        "GetConversationsRequest",
        GetConversationsResponse,
        (
            ("not_joined", bool, False),
            ("last_id", str | None, None),
        ),
    ),
    (
        "SendMessageRequest",
        SendMessageResponse,
        (
            ("conversation_id", str),
            ("content", str),
            ("type", Literal["text", "invite", "media"]),
            _ROOM_ID,
            _WORLD_ID,
            ("media_id", str | None, None),
        ),
    ),
    (
        "GetMessagesRequest",
        GetMessagesResponse,
        (
            ("conversation_id", str),
            ("last_message_id", str | None, None),
        ),
    ),
    ("LeaveConversationRequest", LeaveConversationResponse, (("conversation_id", str),)),
    ("BuyVoiceTimeRequest", BuyVoiceTimeResponse, (("payment_method", _PAYMENT),)),
    (
        "BuyRoomBoostRequest",
        BuyRoomBoostResponse,
        (("payment_method", _PAYMENT), ("amount", int, 1)),
    ),
    ("TipUserRequest", TipUserResponse, (_USER_ID, ("gold_bar", str))),
    ("SetOutfitRequest", SetOutfitResponse, (("outfit", list[Item]),)),
    ("GetInventoryRequest", GetInventoryResponse, ()),
    ("BuyItemRequest", BuyItemResponse, (("item_id", str),)),
    (
        "SendBulkMessageRequest",
        SendBulkMessageResponse,
        (
            ("user_ids", list[str]),
            ("content", str),
            ("type", _TEXT),
            _ROOM_ID,
            _WORLD_ID,
        ),
    ),
    ("MessageMediaRequest", MessageMediaResponse, (("media", MessageMedia),)),
)

__all__ = []
for _name, _response_type, _fields in _REQUESTS:
    globals()[_name] = make_dataclass(
        _name,
        (*_fields, _RID),
        slots=True,
        namespace={
            "__module__": __name__,
            "Response": _response_type,
            _response_type.__name__: _response_type,
        },
    )
    __all__.append(_name)
