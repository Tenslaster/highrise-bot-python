"""Drop-in Highrise namespace backed by the highrise_fast runtime."""

from highrise_fast import *  # noqa: F403
from highrise_fast import (
    AnchorPosition as AnchorPosition,
)
from highrise_fast import (
    BaseBot as _BaseBot,
)
from highrise_fast import (
    Highrise as Highrise,
)
from highrise_fast import (
    Position as Position,
)
from highrise_fast import (
    Reaction as Reaction,
)
from highrise_fast import (
    ResponseError as ResponseError,
)
from highrise_fast import (
    RoomPermissions as RoomPermissions,
)
from highrise_fast import (
    User as User,
)
from highrise_fast import (
    __version__ as __version__,
)

from ._protocol import (
    Incoming as Incoming,
)
from ._protocol import (
    IncomingEvents as IncomingEvents,
)
from ._protocol import (
    Outgoing as Outgoing,
)
from ._protocol import (
    converter as converter,
)
from ._protocol import (
    do_req_resp as do_req_resp,
)
from .webapi import WebAPI as WebAPI


class BaseBot(_BaseBot):
    """A bot with the standard Highrise startup and public Web API behavior."""

    _start_each_session = True
    _webapi_type = WebAPI
