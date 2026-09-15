from dataclasses import dataclass, field
from .tools.logger import LoggerLevel


@dataclass
class ConnectionConfig:
    keepalive_delay: float = 15.0
    request_timeout: float = 10.0
    max_pending_requests: int = 256
    max_message_size: int = 1_048_576
    websocket_max_queue: int = 64
    websocket_write_limit: int = 32_768
    event_queue_size: int = 1000
    event_workers: int = 8
    close_timeout: float = 10.0
    open_timeout: float = 10.0
    min_reconnect_delay: float = 5.0
    max_reconnect_delay: float = 30.0
    reconnect_backoff_factor: float = 2.0
    reconnect_jitter: float = 0.25
    max_reconnect_attempts: int | None = None

    def __post_init__(self) -> None:
        if self.keepalive_delay <= 0:
            raise ValueError("keepalive_delay must be greater than zero")
        if self.request_timeout <= 0:
            raise ValueError("request_timeout must be greater than zero")
        if self.max_pending_requests <= 0:
            raise ValueError("max_pending_requests must be greater than zero")
        if self.max_message_size <= 0:
            raise ValueError("max_message_size must be greater than zero")
        if self.websocket_max_queue <= 0:
            raise ValueError("websocket_max_queue must be greater than zero")
        if self.websocket_write_limit <= 0:
            raise ValueError("websocket_write_limit must be greater than zero")
        if self.event_queue_size <= 0:
            raise ValueError("event_queue_size must be greater than zero")
        if self.event_workers <= 0:
            raise ValueError("event_workers must be greater than zero")
        if self.open_timeout <= 0 or self.close_timeout <= 0:
            raise ValueError("WebSocket timeouts must be greater than zero")
        if self.min_reconnect_delay < 0 or self.max_reconnect_delay < self.min_reconnect_delay:
            raise ValueError("Reconnect delays are invalid")
        if self.reconnect_backoff_factor < 1:
            raise ValueError("reconnect_backoff_factor must be >= 1")
        if not 0 <= self.reconnect_jitter <= 1:
            raise ValueError("reconnect_jitter must be between 0 and 1")


@dataclass
class LoggerConfig:
    name: str = "HighriseBot"
    level: int = LoggerLevel.DEBUG
    show_time: bool = True


@dataclass
class AutoFetchConfig:
    room_users: bool = False
    direct_message: bool = False


@dataclass
class RolesConfig:
    path: str = "./jsons/roles.json"
    autosave_interval: float = 600.0


@dataclass
class BotConfig:
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    logger: LoggerConfig = field(default_factory=LoggerConfig)
    auto_fetch: AutoFetchConfig = field(default_factory=AutoFetchConfig)
    roles: RolesConfig = field(default_factory=RolesConfig)
