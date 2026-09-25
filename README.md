# Highrise Bot Python SDK

<p align="center">
  <strong>Unofficial, performance-focused Python SDK for Highrise bots</strong><br>
  Familiar <code>BaseBot</code> + <code>Highrise</code> programming model, stricter diagnostics, faster serialization paths, and lifecycle tooling.
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Async first" src="https://img.shields.io/badge/Async-first-0A7EA4">
  <img alt="Strict parity" src="https://img.shields.io/badge/Strict%20parity-100%25-2E7D32">
  <img alt="86,352 tests" src="https://img.shields.io/badge/Comprehensive%20suite-86%2C352%2F86%2C352-2E7D32">
  <img alt="100 tests" src="https://img.shields.io/badge/Enterprise%20suite-100%2F100-2E7D32">
  <img alt="Unofficial" src="https://img.shields.io/badge/Highrise-Unofficial-orange">
</p>

<p align="center">
  <code>highrise-bot-python</code> · import <code>highrise_fast</code> · GitHub distribution
</p>

> [!IMPORTANT]
> This project is unofficial. It is not affiliated with, endorsed by, or supported by Highrise or Pocket Worlds.

> [!TIP]
> Want to build a bot in five minutes? Jump to [Quick Start](#quick-start).

---

## What is this?
`highrise_fast` is an independent Python implementation built around the same Highrise bot programming model as the official Python SDK. You still write a `BaseBot`, receive Highrise events through handlers, and call `self.highrise.*` methods for bot actions. The major difference is that this project focuses on the hot path around message parsing, validation, serialization, async request lifecycle, and diagnostics.

The goal is not to make you learn a completely different bot framework. The goal is to keep the mental model familiar while adding developer-oriented capabilities that are useful when a bot has to process lots of events, debug malformed packets, survive long-running async work, or be operated from repeatable launch scripts.

## Start here
| I want to… | Go here |
| --- | --- |
| Make my first bot | [Quick Start](#quick-start) |
| Run it from Windows | [Windows Launcher](#windows-launcher) |
| Migrate an existing official-SDK bot | [Migration](#migration) |
| Understand the extra features | [What `highrise_fast` adds](#what-highrise_fast-adds) |
| See benchmark numbers | [Benchmark Snapshot](#benchmark-snapshot) |
| Debug bad packets | [Validation & Diagnostics](#validation--diagnostics) |
| Tune validation behavior | [Validation Modes](#validation-modes) |
| Build a production layout | [Recommended Project Layout](#recommended-project-layout) |
| Read the deep API reference | [API Reference](#api-reference) |

## Contents
- [At a glance](#at-a-glance)
- [Why use it](#why-use-it)
- [What highrise_fast adds](#what-highrise_fast-adds)
- [Benchmark Snapshot](#benchmark-snapshot)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Windows Launcher](#windows-launcher)
- [Credentials and secrets](#credentials-and-secrets)
- [Bot lifecycle](#bot-lifecycle)
- [Events](#events)
- [Highrise API](#highrise-api)
- [Web API](#web-api)
- [CLI](#cli)
- [Validation & Diagnostics](#validation--diagnostics)
- [Validation Modes](#validation-modes)
- [Invalid Packet Handling](#invalid-packet-handling)
- [Telemetry](#telemetry)
- [Async Task Management](#async-task-management)
- [Request Lifecycle](#request-lifecycle)
- [Serialization](#serialization)
- [Performance Guidance](#performance-guidance)
- [Compatibility](#compatibility)
- [Migration](#migration)
- [Recommended Project Layout](#recommended-project-layout)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Cookbook](#cookbook)
- [API Reference](#api-reference)
- [Data Models](#data-models)
- [Testing](#testing)
- [Benchmarking Your Own Machine](#benchmarking-your-own-machine)
- [Operational Checklist](#operational-checklist)
- [Security](#security)
- [Tradeoffs](#tradeoffs)
- [FAQ](#faq)
- [Credits and links](#credits-and-links)

## At a glance
| Capability | Official `25.1.0` | `highrise_fast` |
| --- | :---: | :---: |
| `BaseBot` programming model | Yes | Yes |
| `Highrise` request surface | Yes | Yes |
| Web API client | Yes | Yes |
| CLI runner | Yes | Yes |
| Room event handlers | Yes | Yes |
| Invalid-packet hook | — | Yes |
| Native strict validation | — | Yes |
| Semantic validation | — | Yes |
| Reason-coded validation errors | — | Yes |
| Fast JSON path with `orjson` | — | Yes, optional |
| Stdlib JSON fallback | Yes | Yes |
| Pending-request cleanup helpers | — | Yes |
| Fire-and-forget mode | — | Yes |
| Runtime telemetry | — | Yes |
| Web API cache support | — | Yes |
| Python baseline documented by this project | 3.10+ | 3.11+ |

Compatibility here means the public bot model and wire-level behavior that this project intentionally tracks. Internal implementation details are different. Do not assume private classes, `attrs` internals, `cattrs` converters, or other official-SDK implementation details are available here.

## Why use it
### Keep the familiar Highrise bot model
You still define a `BaseBot`, override event handlers, and call `self.highrise.*`.

### Spend less time diagnosing malformed packets
Strict validation can point to a concrete JSON path, expected type, received type, value, and reason code.

### Choose your validation policy
Use lenient parsing for speed-sensitive tooling, strict parsing for contract matching, or strict + semantic checks for stronger application-side bounds.

### Handle async lifecycle more explicitly
The implementation tracks pending RPC calls and exposes cleanup helpers for disconnect and state recovery paths.

### Make Windows operation easier
The repository documents repeatable `.bat` setup and restart patterns so a bot can be launched without remembering a long terminal command.

### Measure instead of guessing
Benchmark suites compare the official SDK and the custom implementation across parsing, serialization, validation, memory, async behavior, and endurance workloads.

## What `highrise_fast` adds
### `on_invalid_packet(exc, raw)`
A bot hook for packets that fail receive-loop validation. It can be synchronous or asynchronous.

### Strict receive-loop validation
The default receive loop validates before dispatching the packet to your normal handlers.

### Lenient single-shot parsing
`parse_server_message(data)` remains lenient by default for tooling and controlled experiments.

### Strict single-shot parsing
`parse_server_message(data, strict=True)` raises a structured validation exception when the payload does not satisfy the strict contract.

### Semantic checks
`strict_semantic=True` adds application-oriented bounds such as coordinate ranges, message lengths, finite numeric values, and wallet constraints used by the project.

### Reason codes
Validation issues carry machine-readable categories such as missing-field, wrong-type, invalid-length, and out-of-bounds conditions.

### Path-aware diagnostics
Errors identify where a bad value lives, such as `$.user.id` or `$.position.x`.

### `HighriseFastValidationError` utilities
`.short()`, `.verbose()`, `.to_dict()`, `.errors`, and `.payload` make logging and bug reports easier.

### Pending-request cleanup
`fail_pending()` lets a disconnected client fail all waiting RPC futures instead of leaving callers hanging.

### State synchronization marker
`mark_state_synced()` clears the `state_dirty` marker after you have refreshed state.

### Task manager
`bot.tasks` provides a place for long-lived background work that should shut down with the bot.

### Metrics and invalid-packet counters
`bot.metrics`, `stats()`, and `invalid_packet_stats()` expose runtime visibility.

### Fire-and-forget option
`HR_FAST_FIRE_AND_FORGET` can change outbound request waiting behavior for specific workloads where the ACK is not needed by bot logic.

### Web API cache support
The Web API client supports TTL-based caching, useful for repeated reads.

### Import-compatible request shims
Official-style request objects are exposed for user code that constructs request models, while the live wire path remains optimized independently.

## Benchmark Snapshot
The README intentionally shows only the headline numbers. The detailed harness output belongs in benchmark files and source control, not in the main README. These figures are local SDK microbenchmarks and compatibility tests; they are not measurements of end-to-end Highrise network throughput.

| Test | Recorded result | What it tells you |
| --- | ---: | --- |
| Hot-path correctness suite | 275 / 275 passed | Core parsing, validation, async, outbound, memory, adversarial, and JSON-path checks passed in the recorded run. |
| Oracle parity — adversarial | 250,000 / 250,000 | Strict mode matched the official accept/reject behavior in both directions for the recorded adversarial payload set. |
| Oracle parity — generated | 80,395 / 80,395 | A much broader generated corpus spanning exhaustive, pairwise, triplewise, fuzz, adversarial, and boundary cases matched the oracle. |
| Comprehensive V8 suite | 86,352 / 86,352 | The supplied large-scale suite reported zero failed, error, skipped, or timed-out tests. |
| Enterprise benchmark | 100 / 100 | The supplied 100-test benchmark reported a 100% pass rate. |
| Average speedup | 3.33× | Average custom-vs-official speedup across the 100-test benchmark. |
| Median speedup | 1.15× | Median custom-vs-official speedup across the same benchmark. |
| Serialize vs official | 16.00× CPU · 15.24× wall | Recorded wire serialization comparison on the benchmark machine. |
| Deserialize vs official | 4.00× CPU · 4.16× wall | Recorded deserialization comparison on the benchmark machine. |
| Sustained lenient parse | 2,080,153 ops / 10 s | Approximately 208,015 parses per second in the recorded sustained test, with zero errors. |
| Chat parse p99 | 4.40 µs | High-percentile latency for the recorded ChatEvent parsing case. |
| Cancelled-request leaks | 0 | The recorded cancellation test found no leftover pending-request leak. |
| Object growth over 50k parses | +0 | The recorded object-count audit showed no growth across that workload. |

### How to read those numbers
**Parity is a compatibility number.** It means strict validation agreed with the official SDK used as the oracle in that test harness.

**Ops/s is not bot FPS.** A parser can handle hundreds of thousands of small operations per second while real bots remain limited by WebSocket traffic, Highrise API behavior, network conditions, and your own bot logic.

**Microseconds are hot-path measurements.** They are most useful when you care about overhead inside a message-processing loop.

**A benchmark machine is not universal.** CPU model, Python build, power limits, background processes, and dependency versions can move the result.

**The latest benchmark snapshot should always be regenerated.** Treat the values above as recorded evidence, not a permanent hardware guarantee.

## Installation
```bat
python -m pip install "git+https://github.com/Tenslaster/highrise-bot-python.git"
```

This project is distributed from GitHub rather than PyPI. The documented runtime baseline is Windows 10/11 with Python 3.11+.

| Dependency | Role |
| --- | --- |
| `aiohttp` | WebSocket and Web API networking |
| `orjson` | Recommended fast JSON path; stdlib JSON is available as fallback |
| `quattro` | Optional task-group support; project can fall back to `asyncio.TaskGroup` |

```bat
python -c "import highrise_fast; print(highrise_fast.__version__)"
python -m highrise_fast --help
```

## Quick Start
The shortest useful path is: create a bot class, add one handler, then launch it with a room ID and bot API token.

```python
from highrise_fast import BaseBot, Position

class MyBot(BaseBot):
    async def on_chat(self, user, message):
        if message.lower() == "!ping":
            await self.highrise.chat("pong!")

    async def on_whisper(self, user, message):
        await self.highrise.send_whisper(user.id, f"got it, {user.username}")

    async def on_user_join(self, user, position: Position):
        await self.highrise.chat(f"Welcome, {user.username}!")
```

```bat
python -m highrise_fast my_bot:MyBot YOUR_ROOM_ID YOUR_API_TOKEN
```

The `my_bot:MyBot` syntax means “import `MyBot` from `my_bot.py`”. The official SDK uses the same module/class launch concept; this project keeps that workflow while adding extra runtime controls.

## Windows Launcher
For day-to-day Windows operation, a small launcher is easier than retyping credentials and environment variables every time. The pattern below also gives you a simple restart loop.

### 1. Create a virtual environment
```bat
@echo off
cd /d "%~dp0"
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install "git+https://github.com/Tenslaster/highrise-bot-python.git"
echo Setup complete.
pause
```

### 2. Keep secrets separate
```bat
@echo off
set "ROOM_ID=put_your_room_id_here"
set "API_TOKEN=put_your_bot_token_here"
```

Name that file `bot.env.bat` and add it to `.gitignore`. Do not publish tokens in source code, README files, screenshots, logs, or issue reports.

### 3. Launch and restart automatically
```bat
@echo off
cd /d "%~dp0"

set "VENV=%~dp0venv\Scripts"
call "%~dp0bot.env.bat"

:loop
echo Starting Highrise bot...
"%VENV%\python.exe" -m highrise_fast my_bot:MyBot %ROOM_ID% %API_TOKEN%
echo Bot stopped or disconnected.
echo Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto loop
```

Close the command window or press `Ctrl+C` to stop the launcher. For persistent operation, the repository also documents Startup-folder and log-file patterns.

## Credentials and secrets
The official Highrise workflow requires a bot token and a room ID. The bot must be permitted to enter the target room. Keep the token in an environment or launcher file that is ignored by Git.

```text
my_highrise_bot/
├── my_bot.py
├── bot.env.bat      # secret: never commit
├── Start-Bot.bat
├── Setup-Venv.bat
├── .gitignore
└── venv/
```

```text
bot.env.bat
venv/
logs/
```

## Bot lifecycle
A useful way to understand the runtime is to think in stages: launch, establish the WebSocket session, receive session metadata, process events, send requests, recover from disconnects, and shut down background work.

```text
launcher
   │
   ▼
bot_runner
   │
   ├── before_start(tg)
   │
   ├── WebSocket connection
   │
   ├── on_start(session_metadata)
   │
   ├── receive → validate → parse → dispatch
   │
   ├── bot logic → Highrise requests
   │
   ├── disconnect → fail pending requests
   │
   └── shutdown → stop tasks / close Web API
```

This explicit lifecycle is useful for larger bots because “the bot is connected” and “the bot has a synchronized view of room state” are not necessarily the same thing. The implementation exposes `state_dirty` and `mark_state_synced()` for that distinction.

## Events
Handlers are intentionally familiar. The table below describes the callbacks exposed by `BaseBot`. `on_invalid_packet` is an additional hook for validation failures.

| Handler | What it is for |
| --- | --- |
| `before_start(tg)` | Prepare services and background tasks before a connection attempt. |
| `on_start(session_metadata)` | React to a successful bot session and inspect the supplied session metadata. |
| `on_chat(user, message)` | Handle room chat. |
| `on_whisper(user, message)` | Handle whispers. Whispers are separate from room-wide chat. |
| `on_emote(user, emote_id, receiver)` | React to emote events. |
| `on_reaction(user, reaction, receiver)` | React to reactions. |
| `on_user_join(user, position)` | Run logic when a user joins. |
| `on_user_leave(user)` | Run logic when a user leaves. |
| `on_tip(sender, receiver, tip)` | Handle tip reactions. |
| `on_channel(sender_id, message, tags)` | Handle channel messages. |
| `on_user_move(user, destination)` | Handle movement events; destination can be a position or anchor position. |
| `on_voice_change(users, seconds_left)` | Handle room voice state changes. |
| `on_message(user_id, conversation_id, is_new_conversation)` | Handle direct-message conversation events. |
| `on_moderate(moderator_id, target_user_id, moderation_type, duration)` | Handle moderation events. |
| `on_invalid_packet(exc, raw)` | Extra hook for packets rejected by the validation policy. |

## Highrise API
The public request surface mirrors the official bot API closely. The additional helpers are focused on lifecycle and observability rather than inventing a new request model.

| Method | Purpose |
| --- | --- |
| `chat` | Send room chat. |
| `send_whisper` | Send a private whisper to a user. |
| `send_emote` | Send an emote. |
| `react` | Send a reaction. |
| `set_indicator` | Set the bot room indicator state. |
| `send_channel` | Send a channel message. |
| `walk_to` | Move the bot toward a position or supported anchor destination. |
| `teleport` | Teleport the bot or supported target position. |
| `get_room_users` | Read room users and their positions. |
| `get_wallet` | Read the bot wallet. |
| `get_backpack` | Read backpack data. |
| `change_backpack` | Change backpack state. |
| `moderate_room` | Perform supported room moderation actions. |
| `get_room_privilege` | Read room privileges for a user. |
| `change_room_privilege` | Change room privileges for a user. |
| `move_user_to_room` | Move a user to another room. |
| `get_voice_status` | Read voice status. |
| `add_user_to_voice` | Add a user to voice. |
| `remove_user_from_voice` | Remove a user from voice. |
| `get_user_outfit` | Read a user outfit. |
| `get_my_outfit` | Read the bot outfit. |
| `get_inventory` | Read inventory data. |
| `set_outfit` | Apply an outfit. |
| `buy_item` | Purchase a supported item. |
| `get_conversations` | List conversations available to the bot. |
| `send_message` | Send a conversation message. |
| `send_message_bulk` | Send a supported bulk message operation. |
| `get_messages` | Read conversation messages. |
| `leave_conversation` | Leave a conversation. |
| `buy_voice_time` | Purchase supported voice time. |
| `buy_room_boost` | Purchase a supported room boost. |
| `tip_user` | Send a supported tip. |
| `message_media_upload` | Upload message media using the returned upload flow. |
| `call_in` | Schedule a delayed callback through the bot task group. |

### Additional lifecycle helpers
| Helper | Why it exists |
| --- | --- |
| `fail_pending(message="connection lost")` | Fail all currently pending RPC futures and clear the request registry. |
| `mark_state_synced()` | Clear `state_dirty` after your bot has re-synchronized room state. |

The project also exposes `send_channel(..., only_to=...)`, matching a field available on the official-style `ChannelRequest` model even though the official helper does not expose it in the same way.

```python
await self.highrise.send_channel("ping", tags={"bots"}, only_to={other_bot_id})
```

## Web API
`WebAPI` mirrors the public Web API client surface used by the project. The constructor accepts an optional `base_url`, an optional timeout, and an optional cache TTL. The documented Web API in this repository is unauthenticated; the bot token belongs to the WebSocket bot API path.

```python
from highrise_fast import WebAPI

api = WebAPI()
room = await api.get_room("ROOM_ID")
print(room)

await api.close()
```

The Web API implementation keeps a small TTL cache object. Use caching for repeated reads where stale-for-a-short-time data is acceptable, and disable or shorten the TTL for values that your bot needs to observe immediately.

## CLI
The module runner is designed so a bot can be launched without writing a custom entry point.

```bat
python -m highrise_fast --help
python -m highrise_fast my_bot:MyBot ROOM_ID API_TOKEN
python -m highrise_fast my_bot:MyBot ROOM_ID API_TOKEN --validation strict --on-invalid drop
python -m highrise_fast my_bot:MyBot ROOM_ID API_TOKEN --extra_bot other:Bot OTHER_ROOM OTHER_TOKEN
```

| Option | Use |
| --- | --- |
| `module:Class` | Identify the bot class to run. |
| `ROOM_ID` | Room to connect the bot to. |
| `API_TOKEN` | Bot API token. |
| `--validation strict` | Force strict receive-loop validation. |
| `--validation lenient` | Opt into lenient receive-loop parsing. |
| `--on-invalid drop` | Count/log and drop invalid packets. |
| `--on-invalid log-only` | Log invalid packets but continue processing. |
| `--on-invalid raise` | Fail fast, useful for tests and CI. |
| `--extra_bot ...` | Start an additional bot entry from the same CLI process. |

## Validation & Diagnostics
Validation is one of the biggest developer-experience differences in this project. Instead of turning a malformed packet into a mysterious downstream exception, strict validation can tell you exactly which field failed and why.

```python
from highrise_fast import parse_server_message

event = parse_server_message(data)
event = parse_server_message(data, strict=True)
event = parse_server_message(data, strict=True, strict_semantic=True)
```

| Mode | Meaning |
| --- | --- |
| Lenient | Fast construction; accepts more irregular input when possible. |
| Strict | Enforces the official accept/reject contract used by the oracle tests. |
| Strict + semantic | Strict validation plus project-level bounds and value checks. |

## Validation Modes
There are two layers to understand: the parser function and the live receive loop. `parse_server_message()` defaults to lenient for one-off parsing. The live bot receive loop defaults to strict.

```python
from highrise_fast import BaseBot

class MyBot(BaseBot):
    def __init__(self):
        super().__init__(
            validation_mode="strict",
            on_invalid="drop",
            invalid_warn_cooldown=60.0,
        )
```

### When to choose strict
- You want handlers to receive only payloads that satisfy the tracked contract.

- You are testing protocol compatibility.

- You want malformed packets to become structured diagnostics.

- You are running CI and want failures to be obvious.

### When to choose lenient
- You are writing tooling that intentionally explores malformed input.

- You are prototyping against changing payload shapes.

- You have already accepted the tradeoff that more irregular packets can reach application code.

### Semantic checks
Semantic validation is stricter than simple Python type checking. The recorded test corpus exercises message length limits, coordinate bounds, wallet amount bounds, finite floating-point values, and related consistency rules. This layer is useful when “technically the value has the right Python type” is not enough.

## Invalid Packet Handling
When a live packet fails validation, the runtime applies an explicit policy. The default policy is `drop`, which keeps the bot running, records the failure, and prevents malformed state-changing events from being dispatched as if they were valid.

| Policy | Result |
| --- | --- |
| `drop` | Warn/count, reject pending RPC if a matching request ID exists, increment diagnostics, and keep the bot running. |
| `log-only` | Log the validation failure but continue processing the packet. |
| `raise` | Escalate the validation failure so tests or controlled environments can fail fast. |

```python
class MyBot(BaseBot):
    async def on_invalid_packet(self, exc, raw):
        print("Invalid packet:", exc)
        print("Raw payload:", raw)
```

The hook is intentionally useful for observability. Keep it lightweight; a bad packet should not trigger a second failure caused by expensive or fragile logging code.

## Telemetry
Runtime visibility matters when a bot stays online for hours or days. The implementation exposes metrics objects plus invalid-packet counters so you can answer basic operational questions without instrumenting the entire SDK yourself.

```python
stats = bot.metrics.stats()
invalid = bot.metrics.invalid_packet_stats()
print(stats)
print(invalid)
```

The repository source also tracks counters such as incoming invalid packets and dropped malformed packets. Treat these counters as diagnostics, not as a substitute for your own application metrics.

## Async Task Management
Bots often need background work: periodic status updates, cleanup loops, delayed reminders, music state, moderation windows, or external service polling. The SDK exposes `bot.tasks` so these jobs have a lifecycle owner.

```python
async def status_loop(bot):
    while True:
        await asyncio.sleep(30)
        await bot.highrise.chat("Still online!")

class MyBot(BaseBot):
    async def on_start(self, session_metadata):
        # Use the task manager provided by the SDK.
        self.tasks.create_task(status_loop(self))
```

The important design rule is ownership: tasks started by the bot should be stoppable when the bot shuts down. Avoid raw global tasks that outlive the bot session and keep references to closed clients.

## Request Lifecycle
Every request/response style API needs a strategy for pending operations. This implementation keeps a pending request registry, associates replies with request IDs, and exposes explicit failure cleanup for disconnects.

```text
bot code
   │ await self.highrise.some_method(...)
   ▼
request id assigned
   │
   ▼
pending future stored
   │
   ├── response arrives → resolve future
   │
   └── connection dies → fail_pending() → clear registry
```

This is especially important for bots that issue many concurrent requests. A disconnected socket should not leave a growing set of callers waiting forever.

## Serialization
Outbound messages are serialized to the Highrise wire format. The implementation supports a fast JSON backend when `orjson` is installed and falls back to the standard library when it is unavailable.

| Backend | Intended use |
| --- | --- |
| `orjson` | Fast path when available. |
| stdlib `json` | Compatibility fallback when `orjson` is not available. |

Do not optimize around JSON encoding before measuring your actual bot. For most bots, network latency and application work dominate. The value of the fast path becomes more visible in parse-heavy, event-heavy, or large-batch workloads.

## Performance Guidance
### Do less work inside hot handlers
Keep `on_chat`, `on_user_move`, and similar callbacks short. Dispatch larger jobs to owned background tasks when safe.

### Prefer structured state
Avoid reconstructing the same lookup tables on every message.

### Use strict validation deliberately
Strict mode costs more than lenient mode because it performs more checks. The benefit is predictable input and better diagnostics.

### Batch when the API supports it
Bulk operations can reduce request overhead when the use case allows them.

### Cache read-heavy Web API calls
Use the Web API TTL cache where a short-lived stale value is acceptable.

### Measure before enabling fire-and-forget
Fire-and-forget changes semantics: your code may stop waiting for acknowledgements. It is a performance tool, not a free optimization.

### Keep logs useful
Rate-limited validation logging is more valuable than printing every raw packet forever.

## Compatibility
The official Highrise SDK `25.1.0` is the reference implementation used by this project for compatibility testing. The official package is the supported Pocket Worlds SDK; this repository is an independent implementation.

| Area | Compatibility goal |
| --- | --- |
| Event `_type` names | Track the same wire names. |
| Request `_type` names | Track the same wire names. |
| Handler names | Keep the familiar `BaseBot` callback model. |
| Highrise request methods | Provide the same core public method surface. |
| Web API | Track the same endpoint family exposed by the project. |
| Keepalive / reconnect | Preserve expected session behavior while using different internals. |
| Internal implementation | Intentionally different. |

Compatibility is tested, not inferred from matching function names. When in doubt, test a live bot in a controlled room before changing production traffic.

## Migration
The basic migration is deliberately small: change the import, then verify your bot in a test room.

```python
# official
from highrise import BaseBot

# this project
from highrise_fast import BaseBot
```

| Topic | Migration note |
| --- | --- |
| Package import | `highrise` → `highrise_fast`. |
| Models | Project uses dataclasses/slots rather than the official `attrs` implementation details. |
| Chat vs whisper | Room chat uses `on_chat`; whispers use `on_whisper`. |
| Reaction runtime types | Reaction values are handled as strings at runtime while preserving the supported value set. |
| Web API constructor | Use `WebAPI()` or `WebAPI(base_url=...)`; the project does not use the official-style `token=` constructor parameter. |
| Receive loop | Strict validation is the default here. |
| Core dependency path | The implementation avoids `cattrs` / `pendulum` / `click` on the core hot path. |

Your bot logic is still your responsibility. Protocol parity does not guarantee that a bot built around timing assumptions, undocumented internals, or private SDK behavior will behave identically.

## Recommended Project Layout
```text
my_highrise_bot/
├── my_bot.py
├── config.py
├── services/
│   ├── moderation.py
│   ├── music.py
│   └── storage.py
├── Setup-Venv.bat
├── Start-Bot.bat
├── bot.env.bat          # never commit
├── .gitignore
├── requirements.txt
├── logs/
└── venv/
```

You do not need to copy the `highrise_fast` package into every bot. Install it into your virtual environment and keep your bot code separate from the SDK source.

## Configuration
| Variable | Default | Meaning |
| --- | --- | --- |
| `HR_BOTAPI_URL` | `wss://highrise.game/web/botapi` | Bot WebSocket endpoint. |
| `HR_WEBAPI_URL` | `https://webapi.highrise.game` | Web API base URL. |
| `HR_READ_TIMEOUT` | `60` | WebSocket read timeout in seconds. |
| `HR_WEBAPI_TIMEOUT` | `30` | HTTP timeout for Web API calls. |
| `HR_FAST_FIRE_AND_FORGET` | `0` | Controls the optional fire-and-forget request behavior. |
| `HR_SDK_NAME` | `highrise-fast` | SDK name used by the client. |
| `HR_SDK_USER_AGENT` | project default | Full user-agent value. |
| `SDK_FAST_REQ_TIMEOUT` / `HR_SDK_REQ_TIMEOUT` | `0` | Per-request await timeout; `0` means wait forever. |
| `HIGHRISE_FAST_VALIDATION` | `strict` | Receive-loop mode: `strict` or `lenient`. |
| `HIGHRISE_FAST_ON_INVALID` | `drop` | Invalid-packet policy: `drop`, `raise`, or `log-only`. |
| `HIGHRISE_FAST_INVALID_WARN_COOLDOWN` | `60` | Seconds between identical invalid-packet warnings. |

```bat
set "HR_READ_TIMEOUT=90"
set "HIGHRISE_FAST_VALIDATION=strict"
python -m highrise_fast my_bot:MyBot ROOM_ID TOKEN
```

## Troubleshooting
### `ModuleNotFoundError: highrise_fast`
You installed into a different Python environment. Activate your virtual environment and run `python -m pip show` or reinstall with the same interpreter.

### `python` is not recognized on Windows
Install Python 3.11+ and make sure the Python launcher/interpreter is available on PATH. The README assumes a normal Windows Python installation.

### Bot connects and immediately stops
Check the room ID, token, permissions, Python version, and the first traceback in the console. Do not hide exceptions behind a restart loop until the root cause is understood.

### Bot seems to restart forever
Temporarily remove the `goto loop` behavior from your launcher. Run the module directly so you can see the original traceback.

### No messages reach `on_chat`
Confirm the bot actually connected and that the room is the target room. Remember that whispers use `on_whisper`.

### Validation rejects something unexpected
Log `e.short()` and `e.to_dict()`. The path and reason code are designed to make the mismatch concrete.

### Too many validation warnings
Increase `HIGHRISE_FAST_INVALID_WARN_COOLDOWN` or use a different `on_invalid` policy appropriate to your environment.

### Strict mode is slower than lenient
That is expected. Strict mode performs validation work that lenient mode skips. Use strict when the contract matters; use lenient for tooling that benefits from maximum parser throughput.

### Web API reads are repetitive
Consider a TTL cache through the `WebAPI` client if slightly stale data is acceptable.

### Background tasks keep running after shutdown
Create tasks through the bot/task-manager lifecycle so they can be cancelled and awaited during shutdown.

### A request hangs after a disconnect
The project exposes `fail_pending()` specifically to reject in-flight futures when the transport is gone. Also inspect your own code for swallowed cancellation.

### A token appeared in Git history
Rotate/revoke it in the Highrise creator tooling. Removing the file from the latest commit is not enough if the secret remains in Git history.

## Cookbook
### Ping command
Respond to a simple room command without doing work on every message.

```python
from highrise_fast import BaseBot

class Bot(BaseBot):
    async def on_chat(self, user, message):
        if message.strip().lower() == "!ping":
            await self.highrise.chat("pong!")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Welcome users
React to joins and greet new arrivals.

```python
class Bot(BaseBot):
    async def on_user_join(self, user, position):
        await self.highrise.chat(f"Welcome, {user.username}!")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Private response
Keep a sensitive or noisy response out of the room chat.

```python
class Bot(BaseBot):
    async def on_whisper(self, user, message):
        await self.highrise.send_whisper(user.id, "I received your whisper.")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Invalid packet logging
Capture structured validation failures without printing every raw frame.

```python
class Bot(BaseBot):
    async def on_invalid_packet(self, exc, raw):
        print(exc)
        # Store or send a compact diagnostic here.
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Strict bot configuration
Make the validation policy obvious in source code.

```python
class Bot(BaseBot):
    def __init__(self):
        super().__init__(validation_mode="strict", on_invalid="drop")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Lenient tooling parser
Use the parser directly when exploring payloads.

```python
from highrise_fast import parse_server_message

event = parse_server_message(data)
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Strict tooling parser
Turn malformed input into a structured exception.

```python
from highrise_fast import parse_server_message

try:
    event = parse_server_message(data, strict=True)
except Exception as exc:
    print(exc)
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Strict semantic parser
Add project-level semantic bounds.

```python
event = parse_server_message(data, strict=True, strict_semantic=True)
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Inspect validation details
Print path, expected type, actual type, and reason code.

```python
try:
    parse_server_message(data, strict=True)
except HighriseFastValidationError as e:
    for issue in e.errors:
        print(issue.path, issue.expected, issue.got, issue.reason_code)
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Serialize with the API model
Let the SDK handle wire encoding rather than hand-building JSON strings.

```python
await self.highrise.chat("hello")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Use the Web API
Keep general web reads separate from the bot WebSocket client.

```python
api = WebAPI()
room = await api.get_room("ROOM_ID")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Delayed callback
Schedule a callback through the Highrise client task group.

```python
self.highrise.call_in(lambda: self.highrise.chat("delayed"), delay=5)
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### State resync marker
Tell the runtime that your bot has refreshed its room state.

```python
self.highrise.mark_state_synced()
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Force pending request failure
Reject all currently waiting calls during transport teardown.

```python
self.highrise.fail_pending("connection lost")
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

### Channel targeted delivery
Use the additional `only_to` field exposed by this implementation.

```python
await self.highrise.send_channel("hello", tags={"bots"}, only_to={other_bot_id})
```

Why this pattern works: it keeps bot logic small, makes intent explicit, and uses the SDK feature for the piece of work it was designed to perform.

Common mistake: mixing transport concerns into every event handler. Keep networking, parsing, state, and application logic separated when the bot grows.

Production note: add logging and error handling around your own application behavior. The SDK cannot infer whether a failed database call, third-party API call, or business rule is safe to retry.

## API Reference
The sections below are intentionally repetitive in structure so developers can scan them quickly. They describe the public surface exposed by this project and the practical design considerations around each area. Exact Python type signatures should be read from the installed package version you are using.

<details>
<summary><code>chat</code> — Room-wide text messaging.</summary>

`chat` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `chat` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.chat(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>send_whisper</code> — Private user messaging.</summary>

`send_whisper` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `send_whisper` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.send_whisper(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>send_emote</code> — Emote actions.</summary>

`send_emote` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `send_emote` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.send_emote(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>react</code> — Reaction actions.</summary>

`react` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `react` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.react(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>set_indicator</code> — Room indicator state.</summary>

`set_indicator` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `set_indicator` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.set_indicator(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>send_channel</code> — Channel messaging, with additional targeting support in this project.</summary>

`send_channel` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `send_channel` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.send_channel(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>walk_to</code> — Movement toward a position or supported anchor.</summary>

`walk_to` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `walk_to` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.walk_to(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>teleport</code> — Teleportation-related actions.</summary>

`teleport` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `teleport` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.teleport(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_room_users</code> — Room population and position reads.</summary>

`get_room_users` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_room_users` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_room_users(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_wallet</code> — Wallet lookup.</summary>

`get_wallet` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_wallet` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_wallet(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_backpack</code> — Backpack lookup.</summary>

`get_backpack` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_backpack` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_backpack(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>change_backpack</code> — Backpack changes.</summary>

`change_backpack` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `change_backpack` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.change_backpack(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>moderate_room</code> — Room moderation actions.</summary>

`moderate_room` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `moderate_room` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.moderate_room(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_room_privilege</code> — Privilege lookup.</summary>

`get_room_privilege` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_room_privilege` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_room_privilege(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>change_room_privilege</code> — Privilege changes.</summary>

`change_room_privilege` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `change_room_privilege` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.change_room_privilege(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>move_user_to_room</code> — Cross-room movement.</summary>

`move_user_to_room` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `move_user_to_room` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.move_user_to_room(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_voice_status</code> — Voice-state lookup.</summary>

`get_voice_status` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_voice_status` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_voice_status(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>add_user_to_voice</code> — Voice participant management.</summary>

`add_user_to_voice` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `add_user_to_voice` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.add_user_to_voice(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>remove_user_from_voice</code> — Voice participant removal.</summary>

`remove_user_from_voice` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `remove_user_from_voice` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.remove_user_from_voice(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_user_outfit</code> — User outfit lookup.</summary>

`get_user_outfit` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_user_outfit` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_user_outfit(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_my_outfit</code> — Bot outfit lookup.</summary>

`get_my_outfit` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_my_outfit` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_my_outfit(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_inventory</code> — Inventory lookup.</summary>

`get_inventory` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_inventory` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_inventory(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>set_outfit</code> — Outfit application.</summary>

`set_outfit` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `set_outfit` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.set_outfit(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>buy_item</code> — Item purchasing.</summary>

`buy_item` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `buy_item` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.buy_item(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_conversations</code> — Conversation listing.</summary>

`get_conversations` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_conversations` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_conversations(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>send_message</code> — Conversation messaging.</summary>

`send_message` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `send_message` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.send_message(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>send_message_bulk</code> — Bulk conversation messaging.</summary>

`send_message_bulk` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `send_message_bulk` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.send_message_bulk(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>get_messages</code> — Conversation history retrieval.</summary>

`get_messages` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `get_messages` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.get_messages(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>leave_conversation</code> — Conversation exit.</summary>

`leave_conversation` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `leave_conversation` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.leave_conversation(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>buy_voice_time</code> — Voice-time purchase.</summary>

`buy_voice_time` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `buy_voice_time` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.buy_voice_time(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>buy_room_boost</code> — Room-boost purchase.</summary>

`buy_room_boost` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `buy_room_boost` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.buy_room_boost(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>tip_user</code> — Tip operation.</summary>

`tip_user` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `tip_user` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.tip_user(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>message_media_upload</code> — Media-upload workflow.</summary>

`message_media_upload` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `message_media_upload` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.message_media_upload(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

<details>
<summary><code>call_in</code> — Delayed callback scheduling.</summary>

`call_in` belongs to the public `Highrise` client surface. The important developer experience point is that you call it through `self.highrise` inside your bot rather than manually constructing WebSocket frames.

**Use it when**
Use `call_in` when your bot needs to perform the corresponding Highrise operation. Keep the operation close to the event or service that owns the business rule, rather than scattering unrelated calls across many handlers.

**Typical pattern**
```python
# Inside a BaseBot subclass
result = await self.highrise.call_in(...)
```

**Good practice**
Await the operation unless you deliberately use a fire-and-forget or separately managed task design.

Handle expected application-level errors in your own bot logic.

Avoid issuing the same request repeatedly because multiple handlers saw the same state transition.

Prefer cached or remembered state when the API result does not need to be fresh on every event.

**Performance note**
The SDK benchmark suite measures transport-adjacent overhead, but real request latency also includes Highrise service behavior and network time. A faster serializer does not guarantee a proportionally faster round trip to the server.

**Compatibility note**
The public method name is intentionally familiar to official-SDK users. Internal request objects and serialization paths are not promised to be implementation-identical.

**Failure note**
When the connection drops, the request lifecycle can reject pending operations. Your bot should still treat network failure as a normal runtime possibility and decide whether an application operation is safe to retry.

**See also**
[Request Lifecycle](#request-lifecycle), [Async Task Management](#async-task-management), and [Troubleshooting](#troubleshooting).

</details>

## Handler Reference
<details>
<summary><code>before_start</code></summary>

Called before connection establishment work. Use it to prepare bot-level resources and task ownership.

```python
async def before_start(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_start</code></summary>

Called after session startup information is available.

```python
async def on_start(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_chat</code></summary>

Room chat event. Keep command parsing cheap and move expensive work elsewhere.

```python
async def on_chat(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_whisper</code></summary>

Private whisper event. Do not assume room-wide visibility.

```python
async def on_whisper(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_emote</code></summary>

Emote event with user/emote/receiver context.

```python
async def on_emote(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_reaction</code></summary>

Reaction event with user/reaction/receiver context.

```python
async def on_reaction(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_user_join</code></summary>

User-join event with user and destination position.

```python
async def on_user_join(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_user_leave</code></summary>

User-leave event.

```python
async def on_user_leave(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_tip</code></summary>

Tip reaction event.

```python
async def on_tip(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_channel</code></summary>

Channel message event.

```python
async def on_channel(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_user_move</code></summary>

Movement event; destination may be a position or anchor position.

```python
async def on_user_move(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_voice_change</code></summary>

Voice state event.

```python
async def on_voice_change(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_message</code></summary>

Conversation message event.

```python
async def on_message(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_moderate</code></summary>

Room moderation event.

```python
async def on_moderate(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

<details>
<summary><code>on_invalid_packet</code></summary>

Extra validation-failure hook.

```python
async def on_invalid_packet(self, *args):
    # Keep this callback focused.
    pass
```

Think of handlers as event boundaries. They should translate a Highrise event into one small application action. When a handler grows large, split it into services or background jobs.

For logging, include stable identifiers such as event type, user ID, conversation ID, or request ID when available. Avoid logging secrets.

For performance, avoid expensive synchronous loops inside the handler. Async I/O should be awaited, and repeated work should be deduplicated where possible.

</details>

## Data Models
The public data model includes familiar concepts such as `User`, `Position`, `AnchorPosition`, items, event classes, response classes, and session metadata. The implementation uses dataclasses/slots in places where the official SDK uses different internals.

| Model concept | Developer meaning |
| --- | --- |
| `User` | A Highrise user identity used by event handlers and API calls. |
| `Position` | A coordinate-based room position. |
| `AnchorPosition` | A supported anchor destination representation. |
| Item-like models | Structured inventory/wallet/item information. |
| Event models | Parsed inbound server messages. |
| Response models | Parsed replies to outbound requests. |
| Session metadata | Connection/session information delivered at startup. |

## Testing
The project uses several layers of testing rather than relying on one happy-path test. That is important for an SDK where the dangerous bugs often happen at the edges: wrong Python types, missing fields, malformed JSON, cancellation, deep nesting, invalid floats, semantic bounds, and unexpected combinations of fields.

### Test families used by the project
- **Hot-path unit checks** — designed to answer a different failure question.
- **Oracle parity tests** — designed to answer a different failure question.
- **Exhaustive generated payloads** — designed to answer a different failure question.
- **Pairwise and triplewise combinations** — designed to answer a different failure question.
- **Fuzz-style inputs** — designed to answer a different failure question.
- **Adversarial payloads** — designed to answer a different failure question.
- **Boundary values** — designed to answer a different failure question.
- **Protocol-gap tests** — designed to answer a different failure question.
- **Async concurrency checks** — designed to answer a different failure question.
- **Memory / GC audits** — designed to answer a different failure question.
- **Malformed JSON handling** — designed to answer a different failure question.
- **Sustained endurance tests** — designed to answer a different failure question.
- **Outbound serialization tests** — designed to answer a different failure question.
- **Web API parsing checks** — designed to answer a different failure question.

The recorded comprehensive V8 benchmark reported 86,352 generated and executed tests with 86,352 passes, zero failures, zero errors, zero skips, and zero timeouts. The supplied 100-test enterprise benchmark also reported 100 passes and a 100% pass rate.

## Benchmarking Your Own Machine
Do not copy a benchmark number into a capacity plan without reproducing it on your own hardware. The benchmark is most useful as a comparison between implementations under the same conditions.

```bat
python -m highrise_fast --help
```

Benchmarking checklist: close unrelated CPU-heavy applications, record Python version, record SDK version, keep dependency versions fixed, run several iterations, and compare median/p95/p99 rather than one lucky sample.

## Operational Checklist
- [ ] Create the bot in the Highrise creator tooling.
- [ ] Confirm the target room ID.
- [ ] Keep the API token outside source control.
- [ ] Use a virtual environment.
- [ ] Install a known SDK revision.
- [ ] Run the bot directly before adding an automatic restart loop.
- [ ] Enable strict validation for normal production operation unless your use case requires lenient mode.
- [ ] Add an `on_invalid_packet` hook if you need custom observability.
- [ ] Keep long-lived tasks under bot/task lifecycle ownership.
- [ ] Log enough context to debug failures without recording secrets.
- [ ] Test connection-loss and cancellation behavior.
- [ ] Test the real bot in a controlled room before moving to a production room.
- [ ] Record benchmark conditions when publishing performance claims.

## Security
Treat Highrise tokens as credentials. Do not place them in README files, committed code, screenshots, exception messages, or public benchmark artifacts. The parser’s robustness checks are not a replacement for server-side authorization or application security.

### Secret-handling rules
- Keep `bot.env.bat` ignored by Git.
- Rotate a token immediately if it leaks.
- Avoid dumping entire payloads to logs in production unless you have a clear reason.
- Review third-party libraries before adding them to a bot deployment.
- Run bots under a dedicated Windows account/service context when appropriate for the deployment.

## Tradeoffs
**Unofficial project.** The official SDK remains the supported reference implementation from Pocket Worlds.

**Python baseline is 3.11+.** The official package documents Python 3.10+, while this project documents 3.11+.

**Strict validation costs CPU.** You are paying for stronger input guarantees and diagnostics.

**Import cost can be different.** Native JSON extensions can move cold-start/import behavior.

**Lenient is intentionally broader than strict.** A lenient parser can accept payloads that strict mode rejects.

**Compatibility does not mean private-internals compatibility.** Code that reaches into private official-SDK objects should be migrated carefully.

**Benchmarks are workload-dependent.** Small-message parser numbers do not predict the entire application’s latency.

## FAQ
### Is this the official Highrise SDK?
No. It is an unofficial independent implementation.

### Do I have to rewrite my whole bot?
Usually not for bots that stay on the documented public `BaseBot` and `Highrise` surface. The primary import changes, but you should test your real bot logic.

### Can I use strict validation?
Yes. It is the default receive-loop policy in this project, and `parse_server_message(..., strict=True)` is available for one-off parsing.

### Can I use lenient parsing?
Yes. `parse_server_message()` defaults to lenient, and the receive loop can be configured for lenient mode.

### What does semantic validation do?
It adds value-level bounds and consistency checks beyond simple Python type checking.

### Does `orjson` have to be installed?
No. It is recommended for the fast JSON path; the project can fall back to stdlib JSON.

### Can I run this on Python 3.10?
The project documentation targets Python 3.11+. The official SDK documents Python 3.10+.

### Is 208,015 ops/s the speed my bot will get?
No. It is a local sustained parser microbenchmark, not end-to-end bot throughput.

### Why does strict mode take longer?
It performs more validation work.

### Where are the detailed benchmark reports?
Keep those in the repository’s benchmark materials. The main README is intentionally a summary for usability.

### Can I use a custom Web API URL?
The `WebAPI` constructor supports `base_url=...`.

### How do I debug an invalid packet?
Catch `HighriseFastValidationError` and inspect `.short()`, `.verbose()`, `.to_dict()`, `.errors`, and `.payload`.

### What happens to pending calls after disconnect?
The implementation provides `fail_pending()` so waiting futures can be rejected and the request registry cleared.

### What does `state_dirty` mean?
It is a marker that a stateful invalid event caused the runtime to consider its local state potentially stale; call `mark_state_synced()` after a real resync.

## Credits and links
- Project: https://github.com/Tenslaster/highrise-bot-python
- Official Python SDK: https://github.com/pocketzworld/python-bot-sdk
- Highrise creator documentation: https://create.highrise.game/
- PyPI page for the official SDK: https://pypi.org/project/highrise-bot-sdk/
- JSON library: https://github.com/ijl/orjson

The official SDK is used as the compatibility oracle in the project’s benchmark methodology. The detailed benchmark harnesses and historical measurements should stay in their dedicated repository locations so this README remains a practical entry point rather than a raw test log.

## Developer Deep Dive

<details>
<summary><strong>Open the extended developer handbook</strong> — architecture patterns, diagnostics, production recipes, checklists, and deeper reference material</summary>

This chapter is deliberately more detailed than the top-level guide. GitHub renders it as ordinary documentation, but developers can collapse conceptual sections in their browser using the `<details>` blocks above.

### Command Routing
Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Define the goal.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Make the state transition explicit.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Handle failure separately from success.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Keep the handler small.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Add a focused test.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Measure it before optimizing.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Document the operational assumption.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Re-check behavior after reconnect.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Keep secrets out of logs.** Parse commands early, normalize once, then dispatch to small command functions.

**Command Routing — Prefer deterministic behavior in tests.** Parse commands early, normalize once, then dispatch to small command functions.

### Permissions
Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Define the goal.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Make the state transition explicit.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Handle failure separately from success.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Keep the handler small.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Add a focused test.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Measure it before optimizing.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Document the operational assumption.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Re-check behavior after reconnect.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Keep secrets out of logs.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

**Permissions — Prefer deterministic behavior in tests.** Keep permission decisions separate from chat parsing so changing a role policy does not change every command.

### State Caching
Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Define the goal.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Make the state transition explicit.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Handle failure separately from success.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Keep the handler small.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Add a focused test.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Measure it before optimizing.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Document the operational assumption.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Re-check behavior after reconnect.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Keep secrets out of logs.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

**State Caching — Prefer deterministic behavior in tests.** Cache immutable or slow-changing identifiers, but refresh room-sensitive state after disconnects or malformed stateful events.

### Rate Limiting
Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Define the goal.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Make the state transition explicit.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Handle failure separately from success.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Keep the handler small.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Add a focused test.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Measure it before optimizing.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Document the operational assumption.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Re-check behavior after reconnect.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Keep secrets out of logs.** Protect expensive bot actions by tracking the last execution time per user or command.

**Rate Limiting — Prefer deterministic behavior in tests.** Protect expensive bot actions by tracking the last execution time per user or command.

### Deduplication
Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Define the goal.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Make the state transition explicit.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Handle failure separately from success.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Keep the handler small.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Add a focused test.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Measure it before optimizing.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Document the operational assumption.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Re-check behavior after reconnect.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Keep secrets out of logs.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

**Deduplication — Prefer deterministic behavior in tests.** Use event/request IDs or your own idempotency keys where repeated triggers are possible.

### Retries
Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Define the goal.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Make the state transition explicit.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Handle failure separately from success.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Keep the handler small.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Add a focused test.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Measure it before optimizing.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Document the operational assumption.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Re-check behavior after reconnect.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Keep secrets out of logs.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

**Retries — Prefer deterministic behavior in tests.** Retry only operations that are safe to repeat. A transport timeout does not automatically tell you whether the server processed the original request.

### Background Jobs
Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Define the goal.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Make the state transition explicit.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Handle failure separately from success.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Keep the handler small.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Add a focused test.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Measure it before optimizing.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Document the operational assumption.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Re-check behavior after reconnect.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Keep secrets out of logs.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

**Background Jobs — Prefer deterministic behavior in tests.** Put periodic jobs under a clear owner and shut them down when the bot session ends.

### Logging
Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Define the goal.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Make the state transition explicit.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Handle failure separately from success.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Keep the handler small.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Add a focused test.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Measure it before optimizing.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Document the operational assumption.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Re-check behavior after reconnect.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Keep secrets out of logs.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

**Logging — Prefer deterministic behavior in tests.** Write structured, low-cardinality logs with enough context to reconstruct a failure.

### Metrics
Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Define the goal.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Make the state transition explicit.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Handle failure separately from success.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Keep the handler small.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Add a focused test.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Measure it before optimizing.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Document the operational assumption.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Re-check behavior after reconnect.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Keep secrets out of logs.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

**Metrics — Prefer deterministic behavior in tests.** Count events, failures, reconnects, dropped packets, queue depth, and application-level errors separately.

### Testing
Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Define the goal.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Make the state transition explicit.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Handle failure separately from success.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Keep the handler small.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Add a focused test.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Measure it before optimizing.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Document the operational assumption.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Re-check behavior after reconnect.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Keep secrets out of logs.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

**Testing — Prefer deterministic behavior in tests.** Use fake payloads for parser tests and controlled-room integration tests for behavior tests.

### Configuration
Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Define the goal.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Make the state transition explicit.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Handle failure separately from success.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Keep the handler small.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Add a focused test.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Measure it before optimizing.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Document the operational assumption.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Re-check behavior after reconnect.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Keep secrets out of logs.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

**Configuration — Prefer deterministic behavior in tests.** Use environment variables or a configuration object rather than hard-coding deployment-specific values.

### Feature Flags
Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Define the goal.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Make the state transition explicit.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Handle failure separately from success.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Keep the handler small.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Add a focused test.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Measure it before optimizing.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Document the operational assumption.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Re-check behavior after reconnect.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Keep secrets out of logs.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

**Feature Flags — Prefer deterministic behavior in tests.** Gate optional fast paths such as fire-and-forget behind configuration so deployment behavior is explicit.

## Design Principles
### Familiar API, different internals
Public bot ergonomics should stay familiar while internal performance work remains replaceable.

Implementation note 1: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 2: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 3: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 4: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 5: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 6: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 7: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 8: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 9: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 10: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 11: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 12: Public bot ergonomics should stay familiar while internal performance work remains replaceable. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

### Strict by default at the edge
Malformed external input should be challenged at the transport boundary instead of surprising application code later.

Implementation note 1: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 2: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 3: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 4: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 5: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 6: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 7: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 8: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 9: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 10: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 11: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 12: Malformed external input should be challenged at the transport boundary instead of surprising application code later. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

### Diagnostics are part of the API
An error should help the developer identify where and why the data failed.

Implementation note 1: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 2: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 3: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 4: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 5: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 6: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 7: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 8: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 9: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 10: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 11: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 12: An error should help the developer identify where and why the data failed. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

### Lifecycle ownership
Resources created by the bot should have a clear shutdown owner.

Implementation note 1: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 2: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 3: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 4: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 5: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 6: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 7: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 8: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 9: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 10: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 11: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 12: Resources created by the bot should have a clear shutdown owner. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

### Measure with an oracle
When compatibility matters, compare against an independent reference implementation.

Implementation note 1: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 2: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 3: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 4: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 5: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 6: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 7: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 8: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 9: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 10: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 11: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 12: When compatibility matters, compare against an independent reference implementation. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

### Keep the README actionable
A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs.

Implementation note 1: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 2: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 3: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 4: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 5: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 6: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 7: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 8: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 9: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 10: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 11: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

Implementation note 12: A developer should be able to find install, first run, migration, and troubleshooting without reading benchmark logs. Apply the rule at the boundary where the assumption is easiest to observe, and keep the behavior testable without a live room whenever possible.

## Validation Reason-Code Guide
### `MISSING_FIELD`
`MISSING_FIELD` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `WRONG_TYPE`
`WRONG_TYPE` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `INVALID_LENGTH`
`INVALID_LENGTH` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `OUT_OF_BOUNDS`
`OUT_OF_BOUNDS` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `INVALID_LITERAL`
`INVALID_LITERAL` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `UNKNOWN_TYPE`
`UNKNOWN_TYPE` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `NON_FINITE_NUMBER`
`NON_FINITE_NUMBER` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

### `INVALID_SHAPE`
`INVALID_SHAPE` is a machine-readable label for a class of validation problem. Use the error path together with the reason code; the code alone is not enough to diagnose a packet.

Example 1: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 2: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 3: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 4: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 5: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 6: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

Example 7: first inspect the path, then compare the expected and received representation, then decide whether the producer, parser, or test fixture is wrong.

## Production Patterns
### Safe Startup
Validate configuration before opening the network connection.

1. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Validate configuration before opening the network connection. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Graceful Shutdown
Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically.

1. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Stop background jobs, close clients, and allow awaited requests to finish or fail deterministically. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Controlled Recovery
After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete.

1. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. After connection loss, rebuild derived state rather than assuming the last in-memory snapshot is still complete. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Packet Observability
Count invalid packets by event type and keep a recent diagnostic sample when debugging.

1. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Count invalid packets by event type and keep a recent diagnostic sample when debugging. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### External Integrations
Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled.

1. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Wrap third-party services behind your own interface so SDK lifecycle and external lifecycle do not become coupled. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Persistent State
Write durable state separately from transient room state.

1. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Write durable state separately from transient room state. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Moderation Logic
Separate policy decisions from transport calls so they can be unit tested without Highrise.

1. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Separate policy decisions from transport calls so they can be unit tested without Highrise. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Music / Media Bots
Keep queue state independent from the event loop so a reconnect does not destroy application intent.

1. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Keep queue state independent from the event loop so a reconnect does not destroy application intent. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Multi-Room Bots
Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data.

1. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Give each room a clear state namespace and avoid accidentally sharing mutable room-specific data. The implementation should expose one small responsibility, one failure path, and one observable outcome.

### Benchmark Hygiene
Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command.

1. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

2. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

3. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

4. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

5. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

6. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

7. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

8. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

9. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

10. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

11. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

12. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

13. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

14. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

15. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

16. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

17. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

18. Record Python version, CPU, OS, SDK revision, dependency set, and benchmark command. The implementation should expose one small responsibility, one failure path, and one observable outcome.

## Command-Bot Patterns
### `!ping` — Transport smoke test
Keep `!ping` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!ping"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!ping` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!help` — User-facing command list
Keep `!help` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!help"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!help` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!status` — Operational status
Keep `!status` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!status"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!status` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!uptime` — Process/runtime status
Keep `!uptime` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!uptime"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!uptime` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!users` — Room user lookup
Keep `!users` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!users"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!users` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!where` — Position lookup
Keep `!where` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!where"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!where` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!wallet` — Wallet lookup
Keep `!wallet` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!wallet"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!wallet` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!inventory` — Inventory lookup
Keep `!inventory` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!inventory"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!inventory` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!mod` — Moderation workflow entry point
Keep `!mod` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!mod"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!mod` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

### `!say` — Controlled message relay
Keep `!say` as an application-level command, not as an SDK feature. The bot should parse the message, validate user permission, perform the smallest necessary SDK call, then format the result.

```python
if message.strip().lower().startswith("!say"):
    # 1. validate arguments
    # 2. validate permission
    # 3. perform the SDK operation
    # 4. report the result
    pass
```

Developer note 1: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 2: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 3: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 4: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 5: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 6: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 7: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

Developer note 8: keep `!say` deterministic in tests; isolate external calls behind a small function; never put credentials in command output; treat user-provided arguments as untrusted input.

## Debugging Playbook
### Step 1
Run the bot without the restart loop.

Step 1 diagnostic question 1: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 2: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 3: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 4: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 5: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 6: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 7: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 8: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 9: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 10: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 11: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 12: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 13: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 14: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 15: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 16: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 17: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 18: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 19: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

Step 1 diagnostic question 20: Run the bot without the restart loop. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 2
Confirm Python and package versions.

Step 2 diagnostic question 1: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 2: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 3: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 4: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 5: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 6: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 7: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 8: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 9: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 10: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 11: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 12: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 13: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 14: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 15: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 16: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 17: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 18: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 19: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

Step 2 diagnostic question 20: Confirm Python and package versions. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 3
Confirm room ID and token configuration without printing the token.

Step 3 diagnostic question 1: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 2: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 3: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 4: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 5: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 6: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 7: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 8: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 9: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 10: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 11: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 12: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 13: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 14: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 15: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 16: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 17: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 18: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 19: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

Step 3 diagnostic question 20: Confirm room ID and token configuration without printing the token. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 4
Confirm `on_start` is reached.

Step 4 diagnostic question 1: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 2: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 3: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 4: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 5: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 6: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 7: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 8: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 9: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 10: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 11: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 12: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 13: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 14: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 15: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 16: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 17: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 18: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 19: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

Step 4 diagnostic question 20: Confirm `on_start` is reached. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 5
Confirm a known command reaches `on_chat`.

Step 5 diagnostic question 1: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 2: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 3: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 4: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 5: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 6: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 7: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 8: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 9: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 10: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 11: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 12: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 13: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 14: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 15: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 16: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 17: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 18: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 19: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

Step 5 diagnostic question 20: Confirm a known command reaches `on_chat`. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 6
Enable invalid-packet diagnostics if protocol failures are suspected.

Step 6 diagnostic question 1: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 2: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 3: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 4: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 5: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 6: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 7: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 8: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 9: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 10: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 11: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 12: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 13: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 14: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 15: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 16: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 17: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 18: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 19: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

Step 6 diagnostic question 20: Enable invalid-packet diagnostics if protocol failures are suspected. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 7
Inspect `e.short()` and `e.to_dict()` for path-aware failures.

Step 7 diagnostic question 1: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 2: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 3: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 4: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 5: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 6: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 7: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 8: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 9: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 10: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 11: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 12: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 13: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 14: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 15: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 16: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 17: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 18: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 19: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

Step 7 diagnostic question 20: Inspect `e.short()` and `e.to_dict()` for path-aware failures. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 8
Check pending-request behavior after disconnect.

Step 8 diagnostic question 1: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 2: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 3: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 4: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 5: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 6: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 7: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 8: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 9: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 10: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 11: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 12: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 13: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 14: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 15: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 16: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 17: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 18: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 19: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

Step 8 diagnostic question 20: Check pending-request behavior after disconnect. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 9
Check your own background tasks for cancellation safety.

Step 9 diagnostic question 1: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 2: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 3: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 4: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 5: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 6: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 7: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 8: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 9: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 10: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 11: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 12: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 13: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 14: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 15: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 16: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 17: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 18: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 19: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

Step 9 diagnostic question 20: Check your own background tasks for cancellation safety. Isolate one variable at a time, record the result, and only then change the next variable.

### Step 10
Reproduce in a controlled room before changing production code.

Step 10 diagnostic question 1: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 2: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 3: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 4: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 5: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 6: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 7: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 8: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 9: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 10: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 11: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 12: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 13: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 14: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 15: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 16: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 17: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 18: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 19: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

Step 10 diagnostic question 20: Reproduce in a controlled room before changing production code. Isolate one variable at a time, record the result, and only then change the next variable.

## Reference: Highrise Bot Concepts
### Room
**Room** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Room note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Room note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### User
**User** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

User note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

User note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Position
**Position** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Position note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Position note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### AnchorPosition
**AnchorPosition** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

AnchorPosition note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

AnchorPosition note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Chat
**Chat** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Chat note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Chat note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Whisper
**Whisper** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Whisper note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Whisper note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Emote
**Emote** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Emote note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Emote note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Reaction
**Reaction** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Reaction note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reaction note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Tip
**Tip** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Tip note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Tip note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Voice
**Voice** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Voice note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Voice note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Channel
**Channel** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Channel note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Channel note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Conversation
**Conversation** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Conversation note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Conversation note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Moderation
**Moderation** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Moderation note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Moderation note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Inventory
**Inventory** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Inventory note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Inventory note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Backpack
**Backpack** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Backpack note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Backpack note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Wallet
**Wallet** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Wallet note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Wallet note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Outfit
**Outfit** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Outfit note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Outfit note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Web API
**Web API** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Web API note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Web API note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### WebSocket
**WebSocket** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

WebSocket note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

WebSocket note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Session Metadata
**Session Metadata** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Session Metadata note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Session Metadata note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Request ID
**Request ID** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Request ID note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Request ID note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Pending Request
**Pending Request** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Pending Request note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Pending Request note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Validation
**Validation** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Validation note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Validation note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Semantic Bounds
**Semantic Bounds** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Semantic Bounds note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Semantic Bounds note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Telemetry
**Telemetry** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Telemetry note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Telemetry note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Task Lifecycle
**Task Lifecycle** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Task Lifecycle note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Task Lifecycle note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### Reconnect
**Reconnect** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

Reconnect note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

Reconnect note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

### State Synchronization
**State Synchronization** is a conceptual building block in a Highrise bot. Keep the concept in its own application layer when the bot grows so the event transport does not become the only place where business logic lives.

State Synchronization note 1: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 2: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 3: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 4: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 5: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 6: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 7: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 8: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 9: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 10: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 11: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 12: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 13: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

State Synchronization note 14: define what data is authoritative, what can be cached, what can become stale after reconnect, and what the bot should do when an operation fails.

## Reference: Developer Checklist by Feature
### Chat commands
- [ ] Chat commands: Input accepted?
- [ ] Chat commands: Permission checked?
- [ ] Chat commands: State available?
- [ ] Chat commands: Network operation isolated?
- [ ] Chat commands: Failure path defined?
- [ ] Chat commands: Cancellation safe?
- [ ] Chat commands: Logging useful?
- [ ] Chat commands: No secrets logged?
- [ ] Chat commands: Test exists?
- [ ] Chat commands: Reconnect behavior defined?
- [ ] Chat commands: Latency measured if relevant?
- [ ] Chat commands: User-facing response clear?

### Whispers
- [ ] Whispers: Input accepted?
- [ ] Whispers: Permission checked?
- [ ] Whispers: State available?
- [ ] Whispers: Network operation isolated?
- [ ] Whispers: Failure path defined?
- [ ] Whispers: Cancellation safe?
- [ ] Whispers: Logging useful?
- [ ] Whispers: No secrets logged?
- [ ] Whispers: Test exists?
- [ ] Whispers: Reconnect behavior defined?
- [ ] Whispers: Latency measured if relevant?
- [ ] Whispers: User-facing response clear?

### Welcome messages
- [ ] Welcome messages: Input accepted?
- [ ] Welcome messages: Permission checked?
- [ ] Welcome messages: State available?
- [ ] Welcome messages: Network operation isolated?
- [ ] Welcome messages: Failure path defined?
- [ ] Welcome messages: Cancellation safe?
- [ ] Welcome messages: Logging useful?
- [ ] Welcome messages: No secrets logged?
- [ ] Welcome messages: Test exists?
- [ ] Welcome messages: Reconnect behavior defined?
- [ ] Welcome messages: Latency measured if relevant?
- [ ] Welcome messages: User-facing response clear?

### Moderation
- [ ] Moderation: Input accepted?
- [ ] Moderation: Permission checked?
- [ ] Moderation: State available?
- [ ] Moderation: Network operation isolated?
- [ ] Moderation: Failure path defined?
- [ ] Moderation: Cancellation safe?
- [ ] Moderation: Logging useful?
- [ ] Moderation: No secrets logged?
- [ ] Moderation: Test exists?
- [ ] Moderation: Reconnect behavior defined?
- [ ] Moderation: Latency measured if relevant?
- [ ] Moderation: User-facing response clear?

### Reactions
- [ ] Reactions: Input accepted?
- [ ] Reactions: Permission checked?
- [ ] Reactions: State available?
- [ ] Reactions: Network operation isolated?
- [ ] Reactions: Failure path defined?
- [ ] Reactions: Cancellation safe?
- [ ] Reactions: Logging useful?
- [ ] Reactions: No secrets logged?
- [ ] Reactions: Test exists?
- [ ] Reactions: Reconnect behavior defined?
- [ ] Reactions: Latency measured if relevant?
- [ ] Reactions: User-facing response clear?

### Emotes
- [ ] Emotes: Input accepted?
- [ ] Emotes: Permission checked?
- [ ] Emotes: State available?
- [ ] Emotes: Network operation isolated?
- [ ] Emotes: Failure path defined?
- [ ] Emotes: Cancellation safe?
- [ ] Emotes: Logging useful?
- [ ] Emotes: No secrets logged?
- [ ] Emotes: Test exists?
- [ ] Emotes: Reconnect behavior defined?
- [ ] Emotes: Latency measured if relevant?
- [ ] Emotes: User-facing response clear?

### Movement
- [ ] Movement: Input accepted?
- [ ] Movement: Permission checked?
- [ ] Movement: State available?
- [ ] Movement: Network operation isolated?
- [ ] Movement: Failure path defined?
- [ ] Movement: Cancellation safe?
- [ ] Movement: Logging useful?
- [ ] Movement: No secrets logged?
- [ ] Movement: Test exists?
- [ ] Movement: Reconnect behavior defined?
- [ ] Movement: Latency measured if relevant?
- [ ] Movement: User-facing response clear?

### Voice
- [ ] Voice: Input accepted?
- [ ] Voice: Permission checked?
- [ ] Voice: State available?
- [ ] Voice: Network operation isolated?
- [ ] Voice: Failure path defined?
- [ ] Voice: Cancellation safe?
- [ ] Voice: Logging useful?
- [ ] Voice: No secrets logged?
- [ ] Voice: Test exists?
- [ ] Voice: Reconnect behavior defined?
- [ ] Voice: Latency measured if relevant?
- [ ] Voice: User-facing response clear?

### Tips
- [ ] Tips: Input accepted?
- [ ] Tips: Permission checked?
- [ ] Tips: State available?
- [ ] Tips: Network operation isolated?
- [ ] Tips: Failure path defined?
- [ ] Tips: Cancellation safe?
- [ ] Tips: Logging useful?
- [ ] Tips: No secrets logged?
- [ ] Tips: Test exists?
- [ ] Tips: Reconnect behavior defined?
- [ ] Tips: Latency measured if relevant?
- [ ] Tips: User-facing response clear?

### Inventory
- [ ] Inventory: Input accepted?
- [ ] Inventory: Permission checked?
- [ ] Inventory: State available?
- [ ] Inventory: Network operation isolated?
- [ ] Inventory: Failure path defined?
- [ ] Inventory: Cancellation safe?
- [ ] Inventory: Logging useful?
- [ ] Inventory: No secrets logged?
- [ ] Inventory: Test exists?
- [ ] Inventory: Reconnect behavior defined?
- [ ] Inventory: Latency measured if relevant?
- [ ] Inventory: User-facing response clear?

### Outfits
- [ ] Outfits: Input accepted?
- [ ] Outfits: Permission checked?
- [ ] Outfits: State available?
- [ ] Outfits: Network operation isolated?
- [ ] Outfits: Failure path defined?
- [ ] Outfits: Cancellation safe?
- [ ] Outfits: Logging useful?
- [ ] Outfits: No secrets logged?
- [ ] Outfits: Test exists?
- [ ] Outfits: Reconnect behavior defined?
- [ ] Outfits: Latency measured if relevant?
- [ ] Outfits: User-facing response clear?

### Backpack
- [ ] Backpack: Input accepted?
- [ ] Backpack: Permission checked?
- [ ] Backpack: State available?
- [ ] Backpack: Network operation isolated?
- [ ] Backpack: Failure path defined?
- [ ] Backpack: Cancellation safe?
- [ ] Backpack: Logging useful?
- [ ] Backpack: No secrets logged?
- [ ] Backpack: Test exists?
- [ ] Backpack: Reconnect behavior defined?
- [ ] Backpack: Latency measured if relevant?
- [ ] Backpack: User-facing response clear?

### Wallet
- [ ] Wallet: Input accepted?
- [ ] Wallet: Permission checked?
- [ ] Wallet: State available?
- [ ] Wallet: Network operation isolated?
- [ ] Wallet: Failure path defined?
- [ ] Wallet: Cancellation safe?
- [ ] Wallet: Logging useful?
- [ ] Wallet: No secrets logged?
- [ ] Wallet: Test exists?
- [ ] Wallet: Reconnect behavior defined?
- [ ] Wallet: Latency measured if relevant?
- [ ] Wallet: User-facing response clear?

### Conversations
- [ ] Conversations: Input accepted?
- [ ] Conversations: Permission checked?
- [ ] Conversations: State available?
- [ ] Conversations: Network operation isolated?
- [ ] Conversations: Failure path defined?
- [ ] Conversations: Cancellation safe?
- [ ] Conversations: Logging useful?
- [ ] Conversations: No secrets logged?
- [ ] Conversations: Test exists?
- [ ] Conversations: Reconnect behavior defined?
- [ ] Conversations: Latency measured if relevant?
- [ ] Conversations: User-facing response clear?

### Bulk messaging
- [ ] Bulk messaging: Input accepted?
- [ ] Bulk messaging: Permission checked?
- [ ] Bulk messaging: State available?
- [ ] Bulk messaging: Network operation isolated?
- [ ] Bulk messaging: Failure path defined?
- [ ] Bulk messaging: Cancellation safe?
- [ ] Bulk messaging: Logging useful?
- [ ] Bulk messaging: No secrets logged?
- [ ] Bulk messaging: Test exists?
- [ ] Bulk messaging: Reconnect behavior defined?
- [ ] Bulk messaging: Latency measured if relevant?
- [ ] Bulk messaging: User-facing response clear?

### Media upload
- [ ] Media upload: Input accepted?
- [ ] Media upload: Permission checked?
- [ ] Media upload: State available?
- [ ] Media upload: Network operation isolated?
- [ ] Media upload: Failure path defined?
- [ ] Media upload: Cancellation safe?
- [ ] Media upload: Logging useful?
- [ ] Media upload: No secrets logged?
- [ ] Media upload: Test exists?
- [ ] Media upload: Reconnect behavior defined?
- [ ] Media upload: Latency measured if relevant?
- [ ] Media upload: User-facing response clear?

### Web API reads
- [ ] Web API reads: Input accepted?
- [ ] Web API reads: Permission checked?
- [ ] Web API reads: State available?
- [ ] Web API reads: Network operation isolated?
- [ ] Web API reads: Failure path defined?
- [ ] Web API reads: Cancellation safe?
- [ ] Web API reads: Logging useful?
- [ ] Web API reads: No secrets logged?
- [ ] Web API reads: Test exists?
- [ ] Web API reads: Reconnect behavior defined?
- [ ] Web API reads: Latency measured if relevant?
- [ ] Web API reads: User-facing response clear?

### Scheduled jobs
- [ ] Scheduled jobs: Input accepted?
- [ ] Scheduled jobs: Permission checked?
- [ ] Scheduled jobs: State available?
- [ ] Scheduled jobs: Network operation isolated?
- [ ] Scheduled jobs: Failure path defined?
- [ ] Scheduled jobs: Cancellation safe?
- [ ] Scheduled jobs: Logging useful?
- [ ] Scheduled jobs: No secrets logged?
- [ ] Scheduled jobs: Test exists?
- [ ] Scheduled jobs: Reconnect behavior defined?
- [ ] Scheduled jobs: Latency measured if relevant?
- [ ] Scheduled jobs: User-facing response clear?

### Multi-room operation
- [ ] Multi-room operation: Input accepted?
- [ ] Multi-room operation: Permission checked?
- [ ] Multi-room operation: State available?
- [ ] Multi-room operation: Network operation isolated?
- [ ] Multi-room operation: Failure path defined?
- [ ] Multi-room operation: Cancellation safe?
- [ ] Multi-room operation: Logging useful?
- [ ] Multi-room operation: No secrets logged?
- [ ] Multi-room operation: Test exists?
- [ ] Multi-room operation: Reconnect behavior defined?
- [ ] Multi-room operation: Latency measured if relevant?
- [ ] Multi-room operation: User-facing response clear?

### Reconnect handling
- [ ] Reconnect handling: Input accepted?
- [ ] Reconnect handling: Permission checked?
- [ ] Reconnect handling: State available?
- [ ] Reconnect handling: Network operation isolated?
- [ ] Reconnect handling: Failure path defined?
- [ ] Reconnect handling: Cancellation safe?
- [ ] Reconnect handling: Logging useful?
- [ ] Reconnect handling: No secrets logged?
- [ ] Reconnect handling: Test exists?
- [ ] Reconnect handling: Reconnect behavior defined?
- [ ] Reconnect handling: Latency measured if relevant?
- [ ] Reconnect handling: User-facing response clear?

### Invalid packet handling
- [ ] Invalid packet handling: Input accepted?
- [ ] Invalid packet handling: Permission checked?
- [ ] Invalid packet handling: State available?
- [ ] Invalid packet handling: Network operation isolated?
- [ ] Invalid packet handling: Failure path defined?
- [ ] Invalid packet handling: Cancellation safe?
- [ ] Invalid packet handling: Logging useful?
- [ ] Invalid packet handling: No secrets logged?
- [ ] Invalid packet handling: Test exists?
- [ ] Invalid packet handling: Reconnect behavior defined?
- [ ] Invalid packet handling: Latency measured if relevant?
- [ ] Invalid packet handling: User-facing response clear?

### Metrics
- [ ] Metrics: Input accepted?
- [ ] Metrics: Permission checked?
- [ ] Metrics: State available?
- [ ] Metrics: Network operation isolated?
- [ ] Metrics: Failure path defined?
- [ ] Metrics: Cancellation safe?
- [ ] Metrics: Logging useful?
- [ ] Metrics: No secrets logged?
- [ ] Metrics: Test exists?
- [ ] Metrics: Reconnect behavior defined?
- [ ] Metrics: Latency measured if relevant?
- [ ] Metrics: User-facing response clear?

### Logging
- [ ] Logging: Input accepted?
- [ ] Logging: Permission checked?
- [ ] Logging: State available?
- [ ] Logging: Network operation isolated?
- [ ] Logging: Failure path defined?
- [ ] Logging: Cancellation safe?
- [ ] Logging: Logging useful?
- [ ] Logging: No secrets logged?
- [ ] Logging: Test exists?
- [ ] Logging: Reconnect behavior defined?
- [ ] Logging: Latency measured if relevant?
- [ ] Logging: User-facing response clear?

### Testing
- [ ] Testing: Input accepted?
- [ ] Testing: Permission checked?
- [ ] Testing: State available?
- [ ] Testing: Network operation isolated?
- [ ] Testing: Failure path defined?
- [ ] Testing: Cancellation safe?
- [ ] Testing: Logging useful?
- [ ] Testing: No secrets logged?
- [ ] Testing: Test exists?
- [ ] Testing: Reconnect behavior defined?
- [ ] Testing: Latency measured if relevant?
- [ ] Testing: User-facing response clear?

### Benchmarking
- [ ] Benchmarking: Input accepted?
- [ ] Benchmarking: Permission checked?
- [ ] Benchmarking: State available?
- [ ] Benchmarking: Network operation isolated?
- [ ] Benchmarking: Failure path defined?
- [ ] Benchmarking: Cancellation safe?
- [ ] Benchmarking: Logging useful?
- [ ] Benchmarking: No secrets logged?
- [ ] Benchmarking: Test exists?
- [ ] Benchmarking: Reconnect behavior defined?
- [ ] Benchmarking: Latency measured if relevant?
- [ ] Benchmarking: User-facing response clear?

</details>

## Repository Navigation
The repository itself is organized around the implementation plus a dedicated benchmark area. Keep the README as the entry point, the `highrise_fast/` package as the runtime implementation, and the `Benchmarks/` directory as the place for detailed performance and compatibility artifacts.

| Path | Purpose |
| --- | --- |
| `highrise_fast/` | SDK implementation. |
| `Benchmarks/` | Benchmark/test tooling and detailed benchmark artifacts. |
| `README.md` | Developer and user documentation. |
| `READMEFR.md` | French-language documentation. |
| `SECURITY.md` | Security guidance. |
| `LICENSE.md` | Project license. |

---

<p align="center">
  <strong>Build your bot first. Tune the hot path when you have a reason. Measure everything that matters.</strong>
</p>

