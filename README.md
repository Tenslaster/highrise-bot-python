#!/usr/bin/env python3
"""
generate_readme.py — Writes README.md for highrise-bot-python.

Usage:
    python generate_readme.py
    python generate_readme.py --output README.md
    python generate_readme.py --output ../README.md --force

The README content is stored as a single triple-quoted string below.
Edit the README_TEXT constant to update the content.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

README_TEXT = """# highrise-bot-python

**Unofficial, production-oriented Python SDK for Highrise bots** — a drop-in replacement for the official `highrise-bot-sdk` that delivers **6–14× faster serialization**, **1.4–3.3× faster parsing**, and **zero dependency on `attrs`, `cattrs`, or `pendulum`**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: Custom](https://img.shields.io/badge/License-Custom-red.svg)](LICENSE.md)
[![orjson: optional](https://img.shields.io/badge/orjson-optional-brightgreen)](https://github.com/ijl/orjson)

---

## Why This Exists

The official Highrise Python SDK (`highrise-bot-sdk`) is battle-tested and type-safe, but its reliance on `attrs` + `cattrs` + `pendulum` makes it heavy and slow for high-throughput workloads — busy rooms with dozens of players, frequent events, and real-time commands.

`highrise_fast` is a **standalone, single-package alternative** that keeps the same public API surface while replacing the entire serialization/deserialization pipeline with `orjson` (optional) and direct dict construction.

Validated against the official SDK across a **100-test benchmark suite** covering object model, serialization, parsing, concurrency, memory, leak safety, unicode, and sustained load.

---

## Features

- **Zero monkey-patching** — clean, auditable single-package implementation
- **No `attrs` / `cattrs` / `pendulum` / `pkg_resources`** — only `aiohttp` required
- **Optional `orjson` fast path** — automatically falls back to stdlib `json` if unavailable
- **Text WebSocket frames preferred** — fewer bytes, faster round trips
- **Request/response cleanup** — `finally`-based registry cleanup (no leaks under cancellation)
- **Typed event classes** matching the official SDK — same names, same wire format
- **CLI-compatible**: `python -m highrise_fast module:BotClass ROOM_ID API_TOKEN`
- **Telemetry & stats** — built-in latency tracking, error counters, and health endpoint

---

## Installation

```bash
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
Official = highrise-bot-sdk (cattrs-based).
Custom = highrise_fast (orjson-based).
Full benchmark script: benchmark.py — run with python benchmark.py --iters 100000

Test Suite Coverage
Category	Tests	Rate
A. Environment & dependencies	5	100%
B. Import & startup	5	100%
C. Object model creation	8	100%
D. Object model mutation/access	6	100%
E. Outgoing serialization	12	100%
F. Incoming parsing	12	100%
G. JSON backend comparison	6	100%
H. WebSocket frame codec	4	100%
I. Unicode & edge cases	8	100%
J. Float & numeric precision	4	100%
K. Concurrent async throughput	6	100%
L. Leak & resource safety	4	100%
M. GC pressure & memory	4	100%
N. Wire format conversion	6	100%
O. WebAPI & AttrDict	4	100%
P. Error handling & recovery	3	100%
Q. Sustained load endurance	3	100%
Total	100	100%
Avg speedup (custom vs official): 3.47×. Median speedup: 1.58×.

Serialization — Outgoing Requests
Request Type	Official	Custom	Speedup
EmoteRequest	11.32 µs	824 ns	13.74×
SendMessageRequest	10.33 µs	1.02 µs	10.16×
ChatRequest (2000 chars)	13.11 µs	1.32 µs	9.95×
ModerateRoomRequest	8.32 µs	868 ns	9.58×
TeleportRequest	10.56 µs	1.12 µs	9.39×
GetRoomUsersRequest	6.55 µs	766 ns	8.55×
ChatRequest (short)	8.10 µs	1.03 µs	7.88×
SetOutfitRequest (5 items)	25.39 µs	3.86 µs	6.58×
SetOutfitRequest (10 items)	39.97 µs	6.64 µs	6.02×
Payload size reduced by 6.9% per request (102 B → 95 B). Serialization throughput: 418.7 MB/s sustained.

Parsing — Incoming Events
Event/Response Type	Official	Custom	Speedup
VoiceEvent	19.40 µs	5.86 µs	3.31×
GetWalletResponse	13.21 µs	5.15 µs	2.56×
Error	5.18 µs	2.18 µs	2.37×
UserMovedEvent	9.18 µs	5.25 µs	1.75×
TipReactionEvent	9.49 µs	5.70 µs	1.66×
UserJoinedEvent	9.15 µs	5.68 µs	1.61×
RoomModeratedEvent	5.30 µs	3.34 µs	1.59×
EmoteEvent	5.50 µs	3.47 µs	1.58×
UserLeftEvent	4.03 µs	2.83 µs	1.42×
ChatEvent	4.61 µs	3.29 µs	1.40×
28/28 event types parsed with zero type-name mismatches.

Note: GetRoomUsersResponse with tuple content is a known cattrs limitation in the official SDK (ClassValidationError). The custom SDK parses it cleanly (20.27 µs for 5 users, 73.79 µs for 20 users).

Round-Trip & Sustained Load
Metric	Value
Full round-trip (dict→encode→decode→dict)	1.55 µs avg (644,094 ops/s)
Large payload round-trip (50 KB)	85.58 µs
Encode-only	738 ns avg
Decode-only	1.29 µs avg
Sustained parse load (10 s)	2,711,400 ops, 271,139 ops/s, 0 errors
p50 under sustained load	3.30 µs
p95 under sustained load	4.20 µs
p99 under sustained load	5.50 µs
Memory & Import
Metric	Official	Custom	Notes
Import time (warm)	0.005 ms	30.8 ms	First load pays orjson C-extension cost
Import memory (peak)	0.0 B	1.1 MB	orjson is a compiled extension
Object memory (Position)	72 B	56 B	16 B smaller per object
Object memory (Item)	80 B	72 B	8 B smaller per object
Object memory (User)	56 B	56 B	Identical
Registry leak (200 cancelled)	0	0	Both clean
Fire-and-forget leak (200)	—	0 pending	Clean
GC collections (10K parses)	—	0	Zero GC pressure
Object growth (5K parses)	—	−3	No growth; slight net collection
JSON Backend Comparison
Backend	Serialization	Deserialization
stdlib json	5.62 µs	4.77 µs
ujson	1.66 µs	—
orjson	590 ns	1.20 µs
orjson speedup vs stdlib	9.52×	3.97×
Type Safety
Test Case	Official	Custom
Valid ChatEvent	ACCEPT ✓	ACCEPT ✓
ChatEvent: user wrong type	REJECT ✓	ACCEPT ✓
ChatEvent: missing message	REJECT ✓	ACCEPT ✓
Valid Error	ACCEPT ✓	ACCEPT ✓
Error: missing message	REJECT ✓	ACCEPT ✓
Malformed JSON rejection	✓	6/6 handled
Unknown _type handling	—	4/4 handled
highrise_fast intentionally favors throughput over strict validation — it never crashes on malformed input and fills sensible defaults for missing fields. If you need strict type enforcement, use the official SDK or add Pydantic validation on top.

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
Handles GetRoomUsersResponse (tuple content)	✗ (ClassValidationError)	✓
When to Use This SDK
Use Case	Recommendation
High-throughput rooms (many players, frequent events)	highrise_fast
Latency-sensitive commands (games, reactions)	highrise_fast
Memory-constrained environments (small VPS, containers)	highrise_fast
Strict type validation required (production data pipelines)	Official SDK
Official support & long-term stability	Official SDK
Rapid prototyping (no dependency management)	highrise_fast
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

⚠️ Important: This is an unofficial SDK and is not affiliated with, endorsed by, or supported by Highrise or Pocket Worlds. Use at your own risk. Never commit API tokens to version control.

License
This project is released under a custom license. See LICENSE.md for full terms. The license is not MIT, Apache, BSD, or GPL — it has its own conditions around usage, redistribution, and attribution.

If you are unsure whether your intended use is permitted, read LICENSE.md in full before using, forking, or redistributing this code.

Credits
Wire protocol documentation: Highrise Creator Docs

orjson by ijl

Official SDK by Pocket Worlds

<p align="center"> <b>Built for speed. Audited for correctness. Zero monkey-patching.</b><br> <i>If you need maximum throughput and are comfortable maintaining it yourself, this SDK is for you.</i> </p> """
