"""Regression tests for SDK startup, reconnects, and request lifecycles."""

import asyncio
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import TestServer

import highrise_fast as sdk
from examples.ping_bot import PingBot
from highrise_fast.models_webapi import SearchItemsResponse


class ProtocolTests(unittest.TestCase):
    def test_reference_packets_parse_to_models(self):
        metadata = sdk.parse_server_message(
            {
                "_type": "SessionMetadata",
                "user_id": "bot",
                "room_info": {"owner_id": "owner", "room_name": "Test Room"},
                "rate_limits": {"window": 1},
            },
            strict=True,
        )
        self.assertIsInstance(metadata, sdk.SessionMetadata)
        self.assertEqual(metadata.rate_limits, {"window": 1})
        error = sdk.parse_server_message({"_type": "ErrorResponse", "rid": "3"}, strict=True)
        self.assertIsInstance(error, sdk.Error)
        self.assertEqual((error.message, error.do_not_reconnect, error.rid), ("", False, "3"))
        for name, payload in sdk.BASE_PAYLOADS.items():
            with self.subTest(name=name):
                self.assertNotIsInstance(sdk.parse_server_message(payload, strict=True), dict)

    def test_cli_launches_bots_with_environment_or_positional_tokens(self):
        argv = [
            "highrise-fast", "examples.ping_bot:PingBot", "room",
            "--extra_bot", "examples.ping_bot:PingBot", "other-room", "other-token",
            "--validation", "lenient",
        ]
        with (
            patch.object(sys, "argv", argv),
            patch.dict(os.environ, {"HR_BOT_TOKEN": "primary-token"}),
            patch.object(sdk, "main_async", new_callable=AsyncMock) as runner,
        ):
            sdk.main()
            definitions = runner.await_args.args[0]
            self.assertIsInstance(definitions[0].bot, PingBot)
            self.assertEqual([d.room_id for d in definitions], ["room", "other-room"])
            self.assertEqual([d.api_token for d in definitions], ["primary-token", "other-token"])
            self.assertEqual(os.environ["HIGHRISE_FAST_VALIDATION"], "lenient")


class RoomConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_can_await_rpc_and_rebuild_roster(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        reconnected = asyncio.Event()
        sessions = 0
        subscriptions = []

        class Bot(sdk.BaseBot):
            async def on_start(self, metadata):
                started.set()
                try:
                    await asyncio.Future()
                finally:
                    cancelled.set()

            async def on_reconnected(self):
                await super().on_reconnected()
                self.wallet = await self.highrise.get_wallet()
                reconnected.set()

        def user(uid):
            return {"id": uid, "username": uid}

        position = {"x": 2, "y": 0, "z": 3, "facing": "FrontRight"}

        async def serve(request):
            nonlocal sessions
            sessions += 1
            session_number = sessions
            subscriptions.append(request.query["events"])
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({
                "_type": "SessionMetadata",
                "user_id": "bot",
                "room_info": {"owner_id": "owner", "room_name": "Test Room"},
            })
            async for frame in ws:
                body = json.loads(frame.data)
                rid = body["rid"]
                if body["_type"] == "GetRoomUsersRequest":
                    uid = "old" if session_number == 1 else "new"
                    await ws.send_json({
                        "_type": "GetRoomUsersResponse",
                        "content": [[user(uid), position]], "rid": rid,
                    })
                    if session_number == 1:
                        await started.wait()
                        await ws.close()
                    else:
                        await ws.send_json({
                            "_type": "UserJoinedEvent", "user": user("later"),
                            "position": position,
                        })
                elif body["_type"] == "GetWalletRequest":
                    await ws.send_json({"_type": "GetWalletResponse", "content": [], "rid": rid})
                    await reconnected.wait()
                    await ws.send_json({
                        "_type": "ErrorResponse", "message": "test complete",
                        "do_not_reconnect": True,
                    })
                    await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/bot", serve)
        bot = Bot()
        async with TestServer(app) as server:
            url = str(server.make_url("/bot")).replace("http:", "ws:", 1)
            with patch.object(sdk, "BASE_WS_URL", url), patch.object(
                sdk, "_sleep_backoff", new_callable=AsyncMock
            ):
                await asyncio.wait_for(sdk.bot_runner(bot, "room", "token"), 3)
        self.assertEqual(sessions, 2)
        self.assertTrue(cancelled.is_set())
        self.assertTrue(reconnected.is_set())
        self.assertIsInstance(bot.wallet, sdk.GetWalletResponse)
        self.assertFalse(bot.highrise.state_dirty)
        self.assertEqual(bot.room_tracker.usernames, {"new": "new", "later": "later"})
        self.assertEqual(bot.room_tracker.get_position("later"), (2.0, 0.0, 3.0))
        self.assertEqual(subscriptions, ["user_joined,user_left,user_moved"] * 2)

    async def test_rpc_timeout_covers_socket_send(self):
        class SlowSocket:
            async def send_str(self, data):
                await asyncio.Future()

        hr = sdk.Highrise(ws=SlowSocket())
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(hr._call("GetWalletRequest", timeout=0.02), 0.5)
        self.assertEqual(hr._pending, {})

    async def test_control_reconnect_replaces_stale_instances_and_stops_on_error(self):
        running = {}
        stopped = {}
        attempts = 0

        async def instance_runner(bot, room_id, api_key):
            running.setdefault(room_id, asyncio.Event()).set()
            try:
                await asyncio.Future()
            finally:
                stopped.setdefault(room_id, asyncio.Event()).set()

        async def serve(request):
            nonlocal attempts
            attempts += 1
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            instance_id = "old" if attempts == 1 else "new"
            await ws.send_json({"_type": "ControlSessionMetadata", "instance_ids": [instance_id]})
            await running.setdefault(f"3d/{instance_id}", asyncio.Event()).wait()
            if attempts == 2:
                await stopped.setdefault("3d/old", asyncio.Event()).wait()
                await ws.send_json({"_type": "Error", "message": "done", "do_not_reconnect": True})
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/bot/control/room", serve)
        async with TestServer(app) as server:
            url = str(server.make_url("/bot")).replace("http:", "ws:", 1)
            with (
                patch.object(sdk, "BASE_WS_URL", url),
                patch.object(sdk, "bot_runner", instance_runner),
                patch.object(sdk, "_sleep_backoff", new_callable=AsyncMock),
            ):
                await asyncio.wait_for(sdk.control_runner(sdk.BaseBot, "room", "token"), 3)
        self.assertEqual(attempts, 2)
        self.assertCountEqual(stopped, ["3d/old", "3d/new"])

    async def test_failed_fire_and_forget_send_clears_ack(self):
        class ClosedSocket:
            async def send_str(self, data):
                raise ConnectionResetError("closed")

        hr = sdk.Highrise(ws=ClosedSocket())
        with self.assertRaises(ConnectionError):
            await hr._send_only("ChatRequest", {"message": "test"})
        self.assertEqual(hr._ff_rids, {})

    async def test_dropped_and_cancelled_handlers_release_coroutines(self):
        async def handler():
            await asyncio.Future()

        async with sdk.TaskGroup() as group:
            with patch.object(sdk, "_DISPATCH_MAX_CONCURRENCY", 0):
                discarded = handler()
                self.assertFalse(sdk._spawn_task(group, discarded))
                self.assertIsNone(discarded.cr_frame)

            coroutine = handler()
            tasks = []

            def create(handler):
                task = create_task(handler)
                tasks.append(task)
                return task

            create_task = group.create_task
            with patch.object(group, "create_task", side_effect=create):
                self.assertTrue(sdk._spawn_task(group, coroutine))
            tasks[0].cancel()
        self.assertIsNone(coroutine.cr_frame)
        self.assertEqual(sdk.stats()["dispatch_active"], 0)


class WebAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_search_coalesces_concurrent_calls_and_preserves_color_fields(self):
        queries = []
        entered = asyncio.Event()
        release = asyncio.Event()

        async def search(request):
            queries.append(dict(request.query))
            entered.set()
            await release.wait()
            return web.json_response({
                "items": [{"item_id": "hat", "color_palettes": {"example": [1, 2]}}],
                "total": 1,
            })

        app = web.Application()
        app.router.add_get("/items/search", search)
        async with TestServer(app) as server:
            async with sdk.WebAPI(str(server.make_url("/")), cache_ttl=60) as api:
                cancel = asyncio.create_task(api.search_items("red & blue", limit=10, skip=5))
                await asyncio.wait_for(entered.wait(), 1)
                followers = [
                    asyncio.create_task(api.search_items("red & blue", limit=10, skip=5))
                    for _ in range(10)
                ]
                await asyncio.sleep(0)
                cancel.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await cancel
                release.set()
                results = await asyncio.gather(*followers)
                cached = await api.search_items("red & blue", limit=10, skip=5)
                self.assertTrue(all(result is cached for result in results))
                self.assertIsInstance(cached, SearchItemsResponse)
                self.assertEqual(cached.items[0].color_palettes.example, [1, 2])
                self.assertEqual(cached.total, 1)
            self.assertIsNone(api._session)
        self.assertEqual(queries, [{"query": "red & blue", "limit": "10", "skip": "5"}])

    async def test_invalidating_inflight_read_prevents_stale_cache_write(self):
        old, fresh = asyncio.Event(), asyncio.Event()
        entered = asyncio.Event()
        api = sdk.WebAPI(cache_ttl=60)
        calls = 0

        async def fetch(endpoint):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                await old.wait()
                return sdk._WebPayload("stale")
            await fresh.wait()
            return sdk._WebPayload("current")

        with patch.object(api, "_fetch", side_effect=fetch):
            async with api:
                first = asyncio.create_task(api.send_request("/users/one"))
                await asyncio.wait_for(entered.wait(), 1)
                api.invalidate_cache("/users/one")
                second = asyncio.create_task(api.send_request("/users/one"))
                fresh.set()
                self.assertEqual(await second, "current")
                old.set()
                self.assertEqual(await first, "stale")
                self.assertEqual(await api.send_request("/users/one"), "current")
                self.assertEqual(calls, 2)
