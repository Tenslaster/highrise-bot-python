highrise-bot-python
Unofficial, production-oriented Python SDK for Highrise bots — a drop-in replacement for the official highrise-bot-sdk that delivers up to 14.9× faster serialization, 3.5× faster parsing, and no dependency on attrs, cattrs, or pendulum.

https://img.shields.io/badge/python-3.11%2B-blue
https://img.shields.io/badge/License-MIT-yellow.svg
https://img.shields.io/badge/orjson-optional-brightgreen

Why This Exists
The official Highrise Python SDK (highrise-bot-sdk) is battle-tested and type-safe, but its reliance on attrs + cattrs + pendulum makes it heavy and slow for high-throughput workloads — busy rooms with dozens of players, frequent events, and real-time commands.

highrise_fast is a standalone, single-package alternative that keeps the same public API surface while replacing the entire serialization/deserialization pipeline with orjson (optional) and direct dict construction.

Benchmarked on 500,000 mixed operations across 41 request types, 28 event types, and full round-trip cycles.

Features
Zero monkey-patching — clean, auditable single-package implementation

No attrs / cattrs / pendulum / pkg_resources — only aiohttp required

Optional orjson fast path — automatically falls back to stdlib json if unavailable

Text WebSocket frames preferred — fewer bytes, faster round trips

Request/response cleanup — finally-based registry cleanup (no leaks under cancellation)

Typed event classes matching the official SDK — same names, same wire format

CLI-compatible: python -m highrise_fast module:BotClass ROOM_ID API_TOKEN

Telemetry & stats — built-in latency tracking, error counters, and health endpoint

Installation
bash
# Minimal install (stdlib json fallback)
pip install highrise-bot-python

# With orjson fast path (recommended)
pip install "highrise-bot-python[fast]"

# Development
pip install "highrise-bot-python[dev]"
Requirements: Python 3.11+, aiohttp (required), orjson (optional but strongly recommended).

Quick Start
1. Define a bot
python
from highrise_fast import BaseBot, Highrise

class MyBot(BaseBot):
    async def on_chat(self, user: User, message: str, whisper: bool) -> None:
        if message.lower() == "!ping":
            await self.highrise.chat("pong!")

    async def on_user_join(self, user: User) -> None:
        await self.highrise.chat(f"Welcome, {user.username}!")
2. Run it
bash
python -m highrise_fast my_bot:MyBot YOUR_ROOM_ID YOUR_API_TOKEN
Or programmatically:

python
import asyncio
from highrise_fast import bot_runner

asyncio.run(bot_runner("my_bot:MyBot", "ROOM_ID", "API_TOKEN"))
3. Web API (optional)
python
from highrise_fast import WebAPI

api = WebAPI(token="YOUR_API_TOKEN")
room = await api.get_room("ROOM_ID")
Benchmark Results
All benchmarks run on Python 3.11.9, Windows x64, 8 CPU cores.
Official = highrise-bot-sdk (cattrs-based). Custom = highrise_fast (orjson-based).
Full benchmark script: benchmark.py — run with python benchmark.py --iters 500000

Serialization — Outgoing Requests
Request Type	Official	Custom	Speedup
SendBulkMessageRequest	11,200 ns	750 ns	14.9×
ChannelRequest	9,874 ns	727 ns	13.6×
SetOutfitRequest	10,080 ns	781 ns	12.9×
MessageMediaRequest	10,145 ns	810 ns	12.5×
SendMessageRequest	9,319 ns	760 ns	12.3×
…	…	…	…
TOTAL (all 41 types)	39.4 ms	3.67 ms	10.7×
Payload size also reduced by 5–12 bytes per request (no _type tag overhead).

Parsing — Incoming Events
Event/Response Type	Official	Custom	Speedup
VoiceEvent	15,886 ns	4,597 ns	3.5×
BuyVoiceTimeResponse	8,551 ns	2,498 ns	3.4×
CheckVoiceChatResponse	13,012 ns	3,854 ns	3.4×
GetRoomUsersResponse	28,245 ns	8,987 ns	3.1×
TipUserResponse	8,280 ns	2,670 ns	3.1×
…	…	…	…
28/28 event types parsed with zero type-name mismatches.

Round-Trip & Sustained Load
Metric	Official	Custom	Speedup
Sequential round-trip (avg)	34,496 ns	9,556 ns	3.61×
Sequential round-trip (median)	36,500 ns	9,500 ns	3.84×
Mixed workload (avg, 500K ops)	23,859 ns	4,580 ns	5.21×
P95 (mixed workload)	31,400 ns	6,000 ns	5.23×
P99 (mixed workload)	57,300 ns	7,600 ns	7.54×
Memory & Import
Metric	Official	Custom	Notes
Import time (warm)	0.006 ms	28.4 ms	First load pays orjson C-extension cost
Import memory (peak)	0.0 B	1.1 MB	orjson is a compiled extension
Object memory (Position)	72 B	56 B	16 B smaller per object
Object memory (Item)	80 B	72 B	8 B smaller per object
Registry leak (200 cancelled)	0	0	Both clean
Registry growth (1000 req)	0 pending	0 pending	No leaks under sustained load
Type Safety
Test Case	Official	Custom
Valid ChatEvent	ACCEPT ✓	ACCEPT ✓
ChatEvent: user wrong type	REJECT ✓	ACCEPT ✗
ChatEvent: missing message	REJECT ✓	ACCEPT ✗
Valid Error	ACCEPT ✓	ACCEPT ✓
Error: missing message	REJECT ✓	ACCEPT ✗
Official: 9/11 strict validation. Custom: 4/11 lenient parsing (fills defaults).

highrise_fast intentionally favors throughput over strict validation — it never crashes on malformed input, and fills sensible defaults for missing fields. If you need strict type enforcement, use the official SDK or add Pydantic validation on top.

Feature Parity
Feature	Official	highrise_fast
Highrise class methods	34	35 (+fail_pending)
BaseBot event handlers	13	13 (identical)
Model classes	12	12 (+ Message, Conversation, RoomInfo)
Request types (wire-verified)	41	41 (0 mismatches)
Event types (type-verified)	28	28 (0 mismatches)
No attrs/cattrs dependency	✗	✓
orjson fast path	✗	✓
Finally-based cleanup	✗	✓
Built-in telemetry	✗	✓
When to Use This SDK
Use Case	Recommendation
High-throughput rooms (many players, frequent events)	✅ highrise_fast
Latency-sensitive commands (games, reactions)	✅ highrise_fast
Memory-constrained environments (small VPS, containers)	✅ highrise_fast
Strict type validation required (production data pipelines)	✅ Official SDK
Official support & long-term stability	✅ Official SDK
Rapid prototyping (no dependency management)	✅ highrise_fast
Project Structure
text
highrise_fast/
├── __init__.py          # Core SDK: Highrise class, BaseBot, event dispatch, serialization
├── __main__.py          # CLI entry point: python -m highrise_fast
├── models.py            # Dataclasses: User, Position, Item, Message, Conversation, etc.
├── models_webapi.py     # WebAPI response parsing
└── compat_requests.py   # Compatibility shims for official SDK request classes
Environment Variables
Variable	Default	Purpose
HR_BOTAPI_URL	wss://highrise.game/web/botapi	WebSocket endpoint
HR_WEBAPI_URL	https://webapi.highrise.game	Web API endpoint
HR_READ_TIMEOUT	60	WebSocket read timeout (seconds)
HR_WEBAPI_TIMEOUT	30	HTTP timeout (seconds)
HR_FAST_FIRE_AND_FORGET	0	Set 1 to skip response waiting
HR_SDK_NAME	highrise-fast	SDK name in user-agent
HR_SDK_USER_AGENT	highrise-fast/1.0.0	Full user-agent string
SDK_FAST_REQ_TIMEOUT	0	Request timeout override
Security
See SECURITY.md for supported versions and vulnerability reporting.

Important: This is an unofficial SDK and is not affiliated with, endorsed by, or supported by Highrise or Pocket Worlds. Use at your own risk. Never commit API tokens to version control.

License
MIT License — see LICENSE for details.

Credits
Wire protocol documentation: Highrise Creator Docs

orjson by ijl

Official SDK by Pocket Worlds

<p align="center"> <b>Built for speed. Audited for correctness. Zero monkey-patching.</b><br> <i>If you need maximum throughput and are comfortable maintaining it yourself, this SDK is for you.</i> </p>
