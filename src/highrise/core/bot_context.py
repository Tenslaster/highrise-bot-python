from .bot_ws_requester import WSRequester
from ..cache.cache import CacheManager
from .bot_metrics import Metrics
from ..models.websocket.highrise_models import SessionMetadata, Credentials


class BotContext:
    """SDK-level shared mutable state and dependencies."""

    __slots__ = (
        "requester",
        "session_metadata",
        "credentials",
        "cache",
        "metrics",
    )

    def __init__(self, requester: "WSRequester") -> None:
        self.requester = requester
        self.session_metadata: SessionMetadata | None = None
        self.credentials: Credentials | None = None
        self.cache = CacheManager()
        self.metrics = Metrics()
