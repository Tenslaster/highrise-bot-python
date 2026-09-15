# Changelog

## 3.1.0 — cleanup, bug fixes, perf pass

This release folds in what used to be a separate, unintegrated "V4" layer
(`_v4_core.py` / `_v4_config.py`): those files were never imported by
anything except their own standalone test, so nothing they offered was
actually reaching the bot at runtime. Rather than ship dead code alongside a
working implementation, they were removed and the codebase was cleaned up
and hardened directly.

**Fixed (both are real, verified bugs — reproduced against the prior code
and covered by new regression tests in `tests/test_connection_manager_fixes.py`):**
- `ConnectionManager._handle_raw_frame` referenced `json.JSONDecodeError`
  without ever importing `json`. Any malformed WebSocket frame raised a bare
  `NameError` instead of the intended `InvalidPayloadError`, which bypassed
  the reconnect logic and killed the whole bot session on a single bad
  frame. Now catches `ValueError` (covers both `json.JSONDecodeError` and
  `orjson.JSONDecodeError`).
- `ConnectionManager._event_worker` didn't isolate exceptions raised by a
  bot's own event handlers (`on_chat`, `on_tip`, etc.). One buggy handler
  permanently took a worker out of the pool, silently shrinking event
  throughput over time. Handler exceptions are now caught, logged, and the
  worker keeps running.
- `HighriseApi.__init__` referenced the `BotContext` type without importing
  it anywhere (not even under `TYPE_CHECKING`), unlike the equivalent code
  in `WebApi`. Fixed for consistency and so type-checking tools don't choke
  on it.

**Performance:**
- `slots=True` added to the model classes constructed on every incoming
  event — `User`, `Sender`, `Receiver`, `Position`, `AnchorPosition`,
  `Message`, `Conversation`, `Item`, `CurrencyItem`, `ModerationAction`, and
  `RoomUsersCache`. Lower per-object memory, faster attribute access, no
  behavior change. Request/response models used for outgoing API calls
  (called far less frequently) were left as-is.

**Cleanup / DX:**
- Removed `_v4_core.py`, `_v4_config.py`, and `tests_v4/` (dead, unwired code).
- Removed the accidental double-nested folder structure, `.github/` CI
  workflow (deployed a docs site that isn't part of this package),
  `.pytest_cache/`, and the mdBook `docs/` source tree.
- `User`, `Position`, `AnchorPosition`, `Message`, `Sender`, `Receiver`,
  `Conversation`, `Item`, `CurrencyItem`, `ModerationAction`, `Credentials`,
  `SessionMetadata`, `RoomInfo`, `OutfitItem`, and `RoomPermissions` are now
  re-exported from the top-level `highrise` package, matching the official
  SDK's ergonomics (`from highrise import User` instead of reaching into
  `highrise.models.websocket.highrise_models`).
- Consolidated the old `V2_CHANGELOG.md` and `V3_PERFORMANCE.md` into this file.

## 3.0.0 — throughput & latency pass

Focused on throughput, predictable memory usage, and low latency while
keeping the prior public `BaseBot` API compatible.

- `orjson` used for compact serialization/deserialization (with a stdlib
  `json` fallback if it isn't installed).
- Request IDs are short per-session counters instead of UUIDs.
- One `Future` per request; no one-item `Queue` allocated per request.
- WebSocket frame buffering and SDK event buffering are independently bounded.
- Event handlers run through a fixed worker pool rather than one task per event.
- WebSocket write buffering is configurable.
- Pending requests are capped and cleaned on timeout, cancellation,
  disconnect, and shutdown.

`ConnectionConfig` tuning knobs: `max_pending_requests`, `max_message_size`,
`websocket_max_queue`, `websocket_write_limit`, `event_queue_size`,
`event_workers`, `request_timeout`. More buffering isn't free — it trades
memory and latency under load, so tune based on the room's actual event rate.

## 0.2.0 — reliability pass

- Per-instance request registry with UUID request IDs.
- Request deadlines with guaranteed registry cleanup.
- Explicit connection-loss and timeout errors.
- Persistent versus connection-scoped task management.
- Graceful, idempotent task cancellation.
- Bounded event queue with configurable worker count.
- Event-drop metrics when the queue is full.
- WebSocket incoming message and queue limits.
- Reconnect jitter to reduce reconnect synchronization.
- Incoming frames must decode to JSON objects.
- Web API follows redirects only when explicitly configured (disabled by default).
- Web API responses have bounded error text and JSON validation.
- Login validates non-empty credentials.
- Configuration validates dangerous zero / negative values.
- Roles JSON is schema-checked before loading user IDs.
- Awaiter rejects invalid zero/negative wait counts and timeouts.
- Event handlers execute through the bounded worker pool instead of creating
  an unbounded task per incoming event.
