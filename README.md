# Highrise Bot Python SDK

`highrise_fast` is an unofficial async Python SDK for Highrise bots. It connects
to the Bot API over WebSocket and reads public data through the Web API. It
includes typed bot events, reconnect handling, room tracking, and a shared HTTP
cache. Python 3.11 or newer is required.

[Quick start](#quick-start) · [Bot API](#bot-api) · [Web API](#web-api) ·
[Configuration](#configuration) · [Development](#development)

## Quick start

Install from this repository. The `fast` extra adds the optional `orjson` encoder
and decoder.

```console
python -m pip install --upgrade "highrise-bot-python[fast] @ git+https://github.com/Tenslaster/highrise-bot-python.git"
```

Create a bot token under **Bots & API Keys** in the Highrise Create dashboard,
copy the room ID from the room's share link, and give the bot designer rights
in that room. [Highrise bot setup guide](https://create.highrise.game/learn/bots/guides/creating-a-bot)

Save this as `my_bot.py` in your working directory.

```python
from highrise_fast import BaseBot, SessionMetadata, User


class PingBot(BaseBot):
    async def on_start(self, metadata: SessionMetadata) -> None:
        print(f"Connected to {metadata.room_info.room_name}")

    async def on_chat(self, user: User, message: str) -> None:
        if message.strip().lower() == "!ping":
            await self.highrise.chat(f"Pong, {user.username}!")
```

Set `HR_BOT_TOKEN` in the shell running the bot. Replace `YOUR_ROOM_ID` with the
room ID, then send `!ping` in the room.

**Windows PowerShell**

```powershell
$env:HR_BOT_TOKEN = 'YOUR_BOT_TOKEN'
python -m highrise_fast my_bot:PingBot YOUR_ROOM_ID
```

**Bash**

```bash
export HR_BOT_TOKEN='YOUR_BOT_TOKEN'
python -m highrise_fast my_bot:PingBot YOUR_ROOM_ID
```

The CLI also accepts a positional token and additional bots via
`--extra_bot module:Class ROOM_ID API_TOKEN`. Keep live tokens out of source
control, shared launchers, and logs. For several bots with separately managed
tokens, import their classes and pass a list of `BotDefinition` instances to
`main_async()`.

## Bot API

Access room actions and queries through `self.highrise` after a session starts.

| Area | Methods |
| --- | --- |
| Chat and interactions | `chat`, `send_whisper`, `send_emote`, `react`, `set_indicator`, `send_channel` |
| Movement and presence | `walk_to`, `teleport`, `move_user_to_room`, `get_room_users` |
| Room management | `moderate_room`, `get_room_privilege`, `change_room_privilege`, `buy_room_boost` |
| Voice | `get_voice_status`, `add_user_to_voice`, `remove_user_from_voice`, `buy_voice_time` |
| Items and currency | `get_wallet`, `get_inventory`, `get_backpack`, `change_backpack`, `get_user_outfit`, `get_my_outfit`, `set_outfit`, `buy_item`, `tip_user` |
| Inbox and media | `get_conversations`, `get_messages`, `send_message`, `send_message_bulk`, `leave_conversation`, `message_media_upload` |

Queries such as `get_room_users()` return a typed response or a server
`Error`. Transport timeouts and disconnects can raise exceptions. Commands
that return `None`, such as `chat()` and `send_emote()`, do not return the
server acknowledgement to the caller. Methods such as `tip_user()` may spend
currency. After a time-out, verify the result before retrying those actions.

```python
from highrise_fast import Error

# Inside a BaseBot hook or command
roster = await self.highrise.get_room_users()
if isinstance(roster, Error):
    print(roster.message)
else:
    for user, position in roster.content:
        print(user.username, position)
```

### Events and connection lifecycle

| Hook | When it runs |
| --- | --- |
| `before_start(tg)` | Before each connection attempt. Tasks registered with `tg` are scoped to that attempt. |
| `on_start(metadata)` | When the first room session opens. Metadata includes the bot user ID, room info, and server-provided rate limits. |
| `on_reconnected()` | On later sessions. The default refreshes the roster. Call `await super().on_reconnected()` when overriding the hook to keep that behavior. |
| `on_chat(user, message)`, `on_whisper(user, message)` | Room chat and private room whispers. |
| `on_user_join(user, position)`, `on_user_leave(user)`, `on_user_move(user, destination)` | Changes to room presence and position. |
| `on_emote(user, emote_id, receiver)`, `on_reaction(user, reaction, receiver)`, `on_tip(sender, receiver, tip)` | Avatar interactions. |
| `on_voice_change(users, seconds_left)`, `on_channel(sender_id, message, tags)` | Voice state and bot channel events. |
| `on_message(user_id, conversation_id, is_new_conversation)` | Inbox activity. Use `get_messages()` to read message contents. |
| `on_moderate(moderator_id, target_user_id, moderation_type, duration)` | Room moderation events. |
| `on_invalid_packet(exc, raw)` | A packet failed validation. This hook can be synchronous or async. |

The receive loop runs while startup and reconnect hooks are active, so those
hooks can await Bot API replies. The SDK cancels connection-scoped tasks and
fails pending requests when a connection ends. Use `self.tasks` for work
that should survive reconnects and stop when the bot shuts down. Use
`self.highrise.call_in(callback, delay)` for delayed work scoped to the
current connection.

`self.room_tracker` subscribes to join, leave, and move events and is seeded
from a room snapshot. Until the snapshot arrives, `self.highrise.state_dirty`
is true. A successful later `get_room_users()` refreshes the tracker as the
reply is received. Use `room_tracker.user_count`, `usernames` or
`get_position(user_id)` for repeated local lookups.

The SDK also exposes `self.actions` for throttled actions, `self.prompts` to
await user replies, and `CommandRegistry` for decorated commands.

## Web API

The Web API client works independently of a room connection and uses a
persistent HTTP session. Use it as an async context manager in standalone
scripts. Inside a bot, use `self.webapi`, which the runner closes on shutdown.

```python
import asyncio

from highrise_fast import WebAPI


async def main() -> None:
    async with WebAPI(cache_ttl=60) as api:
        user = await api.get_user_by_username("example")
        if user:
            print(user.username)

        page = await api.search_items("hat", limit=10)
        for item in page.items:
            print(item.item_id, item.item_name, item.get("color_palettes"))


asyncio.run(main())
```

| Data | Methods |
| --- | --- |
| Users | `get_user`, `get_users`, `get_user_by_username`, `username_to_id`, `id_to_username` |
| Rooms | `get_room`, `get_rooms` |
| Posts | `get_post`, `get_posts` |
| Items | `get_item`, `get_items`, `search_items` |
| Grabs | `get_grab`, `get_grabs` |

List endpoints expose cursors such as `last_id` for subsequent pages.
`search_items(query, limit=..., skip=...)` uses offsets and returns an
`items` list and `total` match count. Palette fields are available when
present in the response. [Web API reference](https://create.highrise.game/learn/web-api/general/overview) · [Item search schema](https://create.highrise.game/learn/web-api/endpoints/invoke_search_items)

Identical concurrent GETs share one request when caching is enabled.
Cancelling a single caller leaves the shared request running for the others.
Cached responses are shared objects. Treat them as read-only. Set
`cache_ttl=0` for fresh reads, or use `invalidate_cache()` to refresh cached
data. HTTP failures surface as `ResponseError` and can be retried by the
caller.

## Configuration

```console
python -m highrise_fast my_bot:PingBot YOUR_ROOM_ID --validation strict --on-invalid drop
python -m highrise_fast doctor
```

| Setting | Default | Effect |
| --- | --- | --- |
| `HR_BOT_TOKEN` | — | Token for the CLI's primary bot if omitted from the command line. |
| `HIGHRISE_FAST_VALIDATION` | `strict` | Validate recognized incoming events and correlated replies. Use `lenient` to skip receive-loop validation. |
| `HIGHRISE_FAST_ON_INVALID` | `drop` | Count and drop invalid packets. `log-only` continues processing. `raise` aborts the runner. |
| `HIGHRISE_FAST_INVALID_WARN_COOLDOWN` | `60` | Seconds between identical invalid-packet warnings. |
| `SDK_FAST_REQ_TIMEOUT` / `HR_SDK_REQ_TIMEOUT` | `10` | Seconds allowed for sending an RPC and receiving its reply. The first name takes precedence. Nonpositive values use the 30-second fallback. |
| `HR_READ_TIMEOUT` | `60` | Seconds allowed to wait for the next WebSocket frame. |
| `HR_WEBAPI_TIMEOUT` | `30` | HTTP request timeout in seconds. |
| `HR_WEBAPI_CACHE_TTL` | `60` | Default HTTP cache lifetime in seconds. |
| `HR_FAST_FIRE_AND_FORGET` | `0` | Set to `1` to return from eligible actions after sending the frame. Query methods still await replies. |
| `HR_BOTAPI_URL` / `HR_WEBAPI_URL` | Highrise endpoints | Override the WebSocket or HTTP base URL, for example for local integration tests. |

Explicit `BaseBot` validation settings take precedence over the environment
and CLI defaults. Set environment variables before importing the SDK.

Use `parse_server_message(payload, strict=True)` for offline structural and
semantic checks. `HighriseFastValidationError` includes field paths and
reason codes. Use `invalid_packet_stats()` for validation counters and
`stats()` for transport, dispatch, and latency metrics. The main receive loop
uses structural checks by default.

### Migrating an existing bot

Change imports from `highrise` to `highrise_fast` and run the bot with the
CLI above. For code that expects the `highrise` namespace, call
`highrise_fast.install_alias()` before importing that code. The alias provides
common models and request shims. Test your bot's imports and workflows during
migration. [Runnable alias example](examples/alias_migration.py)

## Development

From a clone, install an editable copy, then run the tests and benchmark.

```console
python -m pip install -e ".[fast,dev]"
python -m unittest discover -s tests -v
python -m highrise_fast self-test
python -m highrise_fast bench
```

The regression suite runs local HTTP and WebSocket servers. It covers CLI
startup, reconnect RPCs, room snapshots, request deadlines, cache
invalidation, and item-search coalescing. `self-test` exercises protocol
fixtures offline. `bench` reports local structural-validation timing.
Highrise service latency, rate limits, and bot handler work also affect
production performance.

For a bot that exits on startup, check room permissions and verify the room
ID and token in the same shell you start it from. Run `doctor` to check SDK
dependencies and connectivity. If the bot stops responding under load,
inspect event-loop lag and keep blocking I/O out of async handlers.

See [examples](examples), the [security policy](SECURITY.md), and the
[Tenslaster Custom License](LICENSE.md).
