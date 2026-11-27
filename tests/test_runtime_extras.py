"""Regression tests for scoped tasks, prompt races, and Web API retries."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import highrise_fast as sdk
from aiohttp import web
from aiohttp.test_utils import TestServer


class KeyedTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_rapid_replacement_waits_for_older_cleanup(self):
        tasks = sdk.TaskManager()
        started = asyncio.Event()
        cleaning = asyncio.Event()
        finish = asyncio.Event()
        order = []

        async def original():
            started.set()
            try:
                await asyncio.Future()
            finally:
                cleaning.set()
                await finish.wait()
                order.append("cleanup")

        async def followup(label):
            order.append(label)

        first = tasks.replace("player", original)
        await asyncio.wait_for(started.wait(), 1)
        skipped = tasks.replace("player", lambda: followup("middle"))
        await asyncio.wait_for(cleaning.wait(), 1)
        last = tasks.replace("player", lambda: followup("last"))
        await asyncio.sleep(0)
        self.assertEqual(order, [])
        finish.set()
        await asyncio.wait_for(last, 1)
        self.assertTrue(first.cancelled())
        self.assertTrue(skipped.cancelled())
        self.assertEqual(order, ["cleanup", "last"])
        await asyncio.sleep(0)
        self.assertFalse(await tasks.cancel_key("player"))

    async def test_keyed_tasks_stop_when_room_client_closes(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def persistent():
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        room = sdk.Highrise(SimpleNamespace(closed=False))
        manager = room.tasks
        manager.replace("loop", persistent)
        await asyncio.wait_for(started.wait(), 1)
        self.assertTrue(room.connected)
        await room._close_session()
        self.assertFalse(room.connected)
        self.assertTrue(cancelled.is_set())
        with self.assertRaises(ConnectionResetError):
            await room.get_room_users()
        with self.assertRaises(RuntimeError):
            manager.replace("another", persistent)

    async def test_runner_closes_room_tasks_and_keeps_bot_tasks_between_sessions(self):
        room_started = asyncio.Event()
        room_stopped = asyncio.Event()
        bot_started = asyncio.Event()
        bot_stopped = asyncio.Event()
        after_reconnect = asyncio.Event()
        sessions = 0

        async def background(started, stopped):
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        class Bot(sdk.BaseBot):
            async def on_start(self, metadata):
                self.tasks.replace("radio", lambda: background(bot_started, bot_stopped))
                self.highrise.tasks.replace(
                    "emotes", lambda: background(room_started, room_stopped)
                )

            async def on_reconnected(self):
                if room_stopped.is_set() and not bot_stopped.is_set() and self.highrise.connected:
                    after_reconnect.set()

        async def serve(request):
            nonlocal sessions
            sessions += 1
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json(
                {
                    "_type": "SessionMetadata",
                    "user_id": "test",
                    "room_info": {"owner_id": "owner", "room_name": "Room"},
                }
            )
            if sessions == 1:
                await room_started.wait()
                await bot_started.wait()
            else:
                await after_reconnect.wait()
                await ws.send_json({"_type": "Error", "message": "done", "do_not_reconnect": True})
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/bot", serve)
        async with TestServer(app) as server:
            url = str(server.make_url("/bot")).replace("http:", "ws:", 1)
            with (
                patch.object(sdk, "BASE_WS_URL", url),
                patch.object(sdk, "_sleep_backoff", new_callable=AsyncMock),
            ):
                await asyncio.wait_for(sdk.bot_runner(Bot(track_room=False), "room", "token"), 3)
        self.assertEqual(sessions, 2)
        self.assertTrue(after_reconnect.is_set())
        self.assertTrue(bot_stopped.is_set())


class PromptTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_catches_reply_before_send_ack(self):
        bot = sdk.BaseBot(track_room=False, enable_prompts=True)
        self.assertEqual(sdk.active_subscriptions(bot), {"chat"})
        sent = asyncio.Event()
        release = asyncio.Event()

        async def whisper(user_id, question):
            sent.set()
            await release.wait()

        bot.highrise = SimpleNamespace(send_whisper=whisper)
        task = asyncio.create_task(bot.prompts.ask(bot, sdk.User("one", "Alice"), "ready?"))
        await asyncio.wait_for(sent.wait(), 1)
        self.assertTrue(bot.prompts.resolve("one", " yes "))
        release.set()
        self.assertEqual(await asyncio.wait_for(task, 1), "yes")
        self.assertFalse(bot.prompts.resolve("one", "later reply"))

    async def test_replaced_prompt_retires_old_waiter_and_cancel_all_clears_new(self):
        bot = sdk.BaseBot()
        user = sdk.User("one", "Alice")
        first = asyncio.create_task(bot.prompts.ask(bot, user, "first?"))
        await asyncio.sleep(0)
        second = asyncio.create_task(bot.prompts.ask(bot, user, "second?"))
        self.assertIsNone(await asyncio.wait_for(first, 1))
        bot.prompts.cancel_all()
        with self.assertRaises(asyncio.CancelledError):
            await second
        self.assertFalse(bot.prompts.resolve("one", "orphaned reply"))


class WebExtrasTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_read_retries_once_and_rejects_an_excessive_wait(self):
        calls = {}

        async def serve(request):
            path = request.path
            calls[path] = calls.get(path, 0) + 1
            if path == "/slow":
                return web.Response(status=429, text="later", headers={"Retry-After": "60"})
            if calls[path] == 1:
                return web.Response(status=503, headers={"Retry-After": "0"})
            return web.json_response({"ok": True})

        app = web.Application()
        app.router.add_get("/{path}", serve)
        async with TestServer(app) as server:
            async with sdk.WebAPI(str(server.make_url("/")), retries=1) as api:
                results = await asyncio.gather(*(api.send_request("/recover") for _ in range(5)))
                self.assertEqual(results, [{"ok": True}] * 5)
                with self.assertRaises(sdk.WebAPIError) as caught:
                    await api.send_request("/slow")
                self.assertIsInstance(caught.exception, sdk.ResponseError)
                self.assertEqual(caught.exception.status, 429)
                self.assertEqual(caught.exception.retry_after, 60.0)
                self.assertEqual(api.cache_info()["http_requests"], 3)
        self.assertEqual(calls, {"/recover": 2, "/slow": 1})

    async def test_resolver_has_bounded_cross_populated_caches(self):
        api = SimpleNamespace(
            username_to_id=AsyncMock(side_effect=["one", "two", "one"]),
            id_to_username=AsyncMock(),
        )
        resolver = sdk.UserResolver(api, maxsize=1)
        self.assertEqual(await resolver.username_to_id("Alice"), "one")
        self.assertEqual(await resolver.id_to_username("one"), "Alice")
        self.assertEqual(await resolver.username_to_id("Bob"), "two")
        self.assertEqual(await resolver.username_to_id("alice"), "one")
        self.assertEqual(api.username_to_id.await_count, 3)
        api.id_to_username.assert_not_awaited()
