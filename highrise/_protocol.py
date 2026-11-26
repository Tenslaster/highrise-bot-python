"""Model serialization and low-level requests for existing Highrise bots."""

from typing import Union

from cattrs.preconf.json import make_converter
from highrise_fast import (
    ChannelEvent,
    ChatEvent,
    EmoteEvent,
    Error,
    Highrise,
    MessageEvent,
    ReactionEvent,
    RoomModeratedEvent,
    SessionMetadata,
    TipReactionEvent,
    UserJoinedEvent,
    UserLeftEvent,
    UserMovedEvent,
    VoiceEvent,
    compat_requests,
)

from ._unions import configure_tagged_union

_requests = tuple(getattr(compat_requests, name) for name in compat_requests.__all__)
Outgoing = Union[_requests]  # noqa: UP007
IncomingEvents = (
    Error
    | ChatEvent
    | EmoteEvent
    | ReactionEvent
    | UserJoinedEvent
    | UserLeftEvent
    | ChannelEvent
    | TipReactionEvent
    | UserMovedEvent
    | VoiceEvent
    | MessageEvent
    | RoomModeratedEvent
)
Incoming = IncomingEvents | Union[tuple(request.Response for request in _requests)]  # noqa: UP007

converter = make_converter()
for _group in (Outgoing, Incoming, SessionMetadata | Error):
    configure_tagged_union(_group, converter)


async def do_req_resp(hr: Highrise, req):
    """Send a typed request through the same correlation and timeout path as Highrise methods."""
    fields = converter.unstructure(req)
    fields.pop("rid")
    return await hr._call(type(req).__name__, fields, request=req)
