from __future__ import annotations

import time


class Metrics:
    """Runtime counters for the current bot session."""

    def __init__(self) -> None:
        self._connected_at: float | None = None
        self._last_latency: float | None = None
        self._events_processed = 0
        self._events_dropped = 0

    def mark_connected(self) -> None:
        self._connected_at = time.monotonic()
        self._last_latency = None
        self._events_processed = 0
        self._events_dropped = 0

    def mark_disconnected(self) -> None:
        self._connected_at = None

    def record_latency(self, seconds: float) -> None:
        self._last_latency = max(0.0, seconds)

    def record_event(self, count: int = 1) -> None:
        self._events_processed += max(0, count)

    def record_dropped_event(self, count: int = 1) -> None:
        self._events_dropped += max(0, count)

    def reset_events(self) -> None:
        self._events_processed = 0
        self._events_dropped = 0

    @property
    def uptime(self) -> float:
        return 0.0 if self._connected_at is None else time.monotonic() - self._connected_at

    @property
    def latency(self) -> float | None:
        return self._last_latency

    @property
    def events_processed(self) -> int:
        return self._events_processed

    @property
    def events_dropped(self) -> int:
        return self._events_dropped
