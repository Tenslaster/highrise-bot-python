# Highrise Bot Python SDK

`highrise_fast` is an unofficial async Python SDK for Highrise bots. It connects
to the Bot API over WebSocket and reads public data through the Web API. It
includes the standard `highrise` package and command, typed bot events, room
tracking, and a shared HTTP cache. Python 3.10 or newer is required.

[Drop-in upgrade](#drop-in-upgrade) · [Quick start](#quick-start) · [Bot API](#bot-api) · [Web API](#web-api) ·
[Configuration](#configuration) · [Development](#development)

## Drop-in upgrade

In the virtual environment where your bot runs, replace Pocket Worlds’
`highrise-bot-sdk` with this distribution. Both provide `highrise`, so use
one SDK per environment. If you keep a `requirements.txt` or lockfile,
replace the old SDK dependency with the Git dependency below.

```powershell
python -m pip uninstall highrise-bot-sdk
python -m pip install --upgrade "highrise-bot-python[fast] @ git+https://github.com/Tenslaster/highrise-bot-python.git"
```

Start your existing bot with its usual command.

```console
highrise mybot:Bot ROOM_ID API_TOKEN
```

The same entry point is available as `python -m highrise`. Existing imports
such as `from highrise import BaseBot`, `from highrise.models import Position`,
and `from highrise.__main__ import bot_runner` work without setup code.
Bots already using the `highrise_fast` package can keep their imports
and the `highrise-fast` command.

Compatibility targets the [Pocket Worlds SDK 25.1.0](https://github.com/pocketzworld/python-bot-sdk/tree/de928597846e678ef14213dbe8516bdfb655ec51).
The two projects publish under different distribution names. This SDK uses
dataclasses for its models. If your bot uses third-party attrs-specific
introspection, use the exported `converter` or Python’s dataclass helpers.

## Quick start

For a new bot, install this SDK in a clean virtual environment. The `fast`
extra adds the optional `orjson` encoder and decoder.

```console
python -m pip install "highrise-bot-python[fast] @ git+https://github.com/Tenslaster/highrise-bot-python.git"
```

Create a bot token under **Bots & API Keys** in the Highrise Create dashboard,
copy the room ID from the room's share link, and give the bot designer rights
in that room. [Highrise bot setup guide](https://create.highrise.game/learn/bots/guides/creating-a-bot)

Save this as `my_bot.py` in your working directory.

```python
from highrise import BaseBot, SessionMetadata, User


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
highrise my_bot:PingBot YOUR_ROOM_ID
```

**Bash**

```bash
export HR_BOT_TOKEN='YOUR_BOT_TOKEN'
highrise my_bot:PingBot YOUR_ROOM_ID
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
such as `chat()` and `send_emote()` return `None` on success and raise
`ResponseError` if the server rejects the action in the default acknowledged
mode. Methods such as `tip_user()` may spend currency. After a time-out, verify the result before retrying those actions.

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
| `on_start(metadata)` | When a room session opens. `highrise.BaseBot` calls it again on reconnect, as in the original SDK. `highrise_fast.BaseBot` calls it on the first session. |
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

Session metadata includes the connection ID and bot user ID, room info, and
server-provided rate limits. Named limits use `(limit, period)` pairs.

`self.room_tracker` subscribes to join, leave, and move events and is seeded
from a room snapshot. Until the snapshot arrives, `self.highrise.state_dirty`
is true. A successful later `get_room_users()` refreshes the tracker as the
reply is received. Use `room_tracker.user_count`, `usernames` or
`get_position(user_id)` for repeated local lookups.

`get_username(user_id)` and `get_anchor(user_id)` read the same local state.
`get_nearby(x, z, radius)` works on floor coordinates. A bot that does not
need the tracker can call `super().__init__(track_room=False)` to skip the
automatic startup roster read and the tracker’s event subscriptions.

The SDK also exposes `self.actions` for throttled actions, `self.prompts` to
await user replies, and `CommandRegistry` for decorated commands.
`DebouncedSaver` coalesces state updates, serializes writes, and flushes the
latest pending update when you await `stop()`.

## Web API

The Web API client works independently of a room connection and uses a
persistent HTTP session. Use it as an async context manager in standalone
scripts. Inside a bot, use `self.webapi`, which the runner closes on shutdown.
`highrise.webapi.WebAPI` returns the named models in `highrise.models_webapi`.
`highrise_fast.WebAPI` provides attribute access and raw data for flexible
queries.

```python
import asyncio

from highrise.webapi import WebAPI


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

`WebAPI(cache_size=256)` caps retained responses. `cache_size=0` keeps
concurrent request sharing with a positive TTL and stores zero responses
after each request completes. Use `api.cache_info()` to inspect cache hits,
misses, shared reads, and outgoing requests.

Stream cursor-based collections with `iter_items`, `iter_users`,
`iter_rooms`, `iter_posts`, or `iter_grabs`. Each iterator accepts the
corresponding `get_*` filters plus `page_size` and `max_items`. [Web API pagination](https://create.highrise.game/learn/web-api/general/overview)

```python
# Inside an async function with a WebAPI client
async for item in api.iter_items(category="hat", page_size=20, max_items=60):
    print(item.item_id, item.item_name)
```

## Configuration

```console
highrise my_bot:PingBot YOUR_ROOM_ID --validation strict --on-invalid drop
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

### Sending a typed request

The low-level interface uses the same connection, timeout, and request
correlation code as `self.highrise`'s convenience methods.

```python
from highrise import do_req_resp
from highrise.models import GetWalletRequest

# Inside a bot handler
wallet = await do_req_resp(self.highrise, GetWalletRequest())
if isinstance(wallet, GetWalletRequest.GetWalletResponse):
    print(wallet.content)
```

Use `highrise.converter` with `Outgoing` or `Incoming` to encode or decode
protocol objects in an offline tool.

## Development

From a clone, install an editable copy, then run the tests and benchmark.

```console
python -m pip install -e ".[fast,dev]"
python -m unittest discover -s tests -v
python -m highrise_fast self-test
python -m highrise_fast bench
```

The regression suite runs local HTTP and WebSocket servers. It covers an
unchanged `highrise` bot launched in a fresh interpreter, reconnect RPCs,
typed Web API responses, request deadlines, cache invalidation, and
item-search coalescing. `self-test` exercises protocol
fixtures offline. `bench` reports local structural-validation timing.
Highrise service latency, rate limits, and bot handler work also affect
production performance.

For a bot that exits on startup, check room permissions and verify the room
ID and token in the same shell you start it from. Run `doctor` to check SDK
dependencies and connectivity. If the bot stops responding under load,
inspect event-loop lag and keep blocking I/O out of async handlers.

See [examples](examples), the [security policy](SECURITY.md), and the
[Tenslaster Custom License](LICENSE.md).
