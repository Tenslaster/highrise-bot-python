"""Public exception hierarchy for the Highrise SDK."""


class HighriseError(Exception):
    """Base class for SDK errors."""


class BotStateError(HighriseError):
    """Raised when an operation isn't valid for the current bot state."""


class NotConnectedError(BotStateError):
    """Raised when a request is attempted without an open WebSocket."""


class BotShuttingDownError(BotStateError):
    """Raised when an operation is attempted while the bot is shutting down."""


class RequestError(HighriseError):
    """Base class for request failures."""


class RequestTimeoutError(RequestError):
    """Raised when the server doesn't answer before the request deadline."""


class RequestCancelledError(RequestError):
    """Raised when a request is cancelled because its task or session ends."""


class ConnectionLostError(RequestError):
    """Raised for requests interrupted by a connection loss."""


class RequestCapacityError(RequestError):
    """Raised when the pending-request safety limit is reached."""


class InvalidPayloadError(HighriseError):
    """Raised when an incoming frame has an invalid JSON/object shape."""


class EventQueueFullError(HighriseError):
    """Raised when the event queue reaches its configured safety limit."""


class WebAPIError(HighriseError):
    """Base class for Web API failures."""
