from __future__ import annotations

import time


class Metrics:
    """Runtime counters for the current bot session and lifetime totals.

    Per-session counters (events_processed, events_dropped, latency, uptime)
    are reset on every reconnect so they always reflect the current session.

    Lifetime counters (lifetime_events_processed, lifetime_events_dropped)
    accumulate across all reconnects and are never reset for the lifetime of
    the Metrics instance.
    """

    __slots__ = (
        "_connected_at",
        "_last_latency",
        "_peak_latency",
        "_events_processed",
        "_events_dropped",
        "_lifetime_events_processed",
        "_lifetime_events_dropped",
    )

    def __init__(self) -> None:
        self._connected_at: float | None = None
        self._last_latency: float | None = None
        self._peak_latency: float | None = None

        # Per-session counters — reset on each reconnect.
        self._events_processed = 0
        self._events_dropped = 0

        # Lifetime counters — never reset.
        self._lifetime_events_processed = 0
        self._lifetime_events_dropped = 0

    def mark_connected(self) -> None:
        self._connected_at = time.monotonic()
        self._last_latency = None
        self._peak_latency = None
        self._events_processed = 0
        self._events_dropped = 0

    def mark_disconnected(self) -> None:
        self._connected_at = None

    def record_latency(self, seconds: float) -> None:
        clamped = max(0.0, seconds)
        self._last_latency = clamped
        if self._peak_latency is None or clamped > self._peak_latency:
            self._peak_latency = clamped

    def record_event(self, count: int = 1) -> None:
        n = max(0, count)
        self._events_processed += n
        self._lifetime_events_processed += n

    def record_dropped_event(self, count: int = 1) -> None:
        n = max(0, count)
        self._events_dropped += n
        self._lifetime_events_dropped += n

    def reset_events(self) -> None:
        self._events_processed = 0
        self._events_dropped = 0

    @property
    def uptime(self) -> float:
        return 0.0 if self._connected_at is None else time.monotonic() - self._connected_at

    @property
    def latency(self) -> float | None:
        """Round-trip time of the last keepalive in seconds, or None."""
        return self._last_latency

    @property
    def peak_latency(self) -> float | None:
        """Highest observed keepalive round-trip this session, or None."""
        return self._peak_latency

    @property
    def events_processed(self) -> int:
        """Events dispatched since the current connection was established."""
        return self._events_processed

    @property
    def events_dropped(self) -> int:
        """Events dropped (queue full) since the current connection was established."""
        return self._events_dropped

    @property
    def lifetime_events_processed(self) -> int:
        """Total events dispatched across all connections since bot startup."""
        return self._lifetime_events_processed

    @property
    def lifetime_events_dropped(self) -> int:
        """Total events dropped across all connections since bot startup."""
        return self._lifetime_events_dropped
