"""Regression coverage for command routing, action lanes, roster events, and caches."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import highrise_fast as sdk
from aiohttp import web
from aiohttp.test_utils import TestServer


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_alias_cooldown_source_and_private_replies(self):
        registry = sdk.CommandRegistry(cooldown_maxsize=2)
        bot = sdk.BaseBot(track_room=False)
        bot.command_registry = registry
        bot.highrise = SimpleNamespace(chat=AsyncMock(), send_whisper=AsyncMock())
        player = sdk.User("one", "Alice")
        calls = []
        registry.set_permission_checker(lambda bot, user, rank: rank == "mod")

        @registry.command("Test", aliases=["T"], cooldown=60, rank="mod", sources={"chat"})
        async def command(ctx):
            """Send a private test response."""
            calls.append(ctx.args)
            await ctx.reply_private("confirmed")

        self.assertEqual(sdk.active_subscriptions(bot), {"chat"})
        self.assertIs(registry.get_command("T"), command)
        self.assertTrue(await registry.handle(bot, player, "!T first second"))
        bot.highrise.send_whisper.assert_awaited_once_with("one", "confirmed")
        self.assertTrue(await registry.handle(bot, player, "!test again"))
        self.assertIn("Wait", bot.highrise.chat.await_args.args[0])
        self.assertTrue(await registry.handle(bot, player, "!T", source="whisper"))
        self.assertIn("unavailable", bot.highrise.send_whisper.await_args.args[1])
        self.assertEqual(calls, [["first", "second"]])
        self.assertTrue(registry.remove_command("T"))
        self.assertFalse(await registry.handle(bot, player, "!test"))
        self.assertFalse(registry.has_commands)

    async def test_dm_uses_newest_matching_sender_and_skips_replays(self):
        bot = sdk.BaseBot()
        bot.highrise = connection = sdk.Highrise(my_id="bot")
        registry = SimpleNamespace(prefix="!", handle=AsyncMock())
        latest = sdk.Message(message_id="2", content="hello", sender_id="one")
        old = sdk.Message(message_id="1", content="!old", sender_id="one")
        connection.get_messages = AsyncMock(return_value=sdk.GetMessagesResponse([latest, old]))
        await sdk._route_dm_command(bot, connection, "one", "room", registry)
        registry.handle.assert_not_awaited()

        latest.content = "!new"
        await sdk._route_dm_command(bot, connection, "other", "room", registry)
        registry.handle.assert_not_awaited()
        await asyncio.gather(
            sdk._route_dm_command(bot, connection, "one", "room", registry),
            sdk._route_dm_command(bot, connection, "one", "room", registry),
        )
        registry.handle.assert_awaited_once_with(
            bot, sdk.User("one", "one"), "!new", source="dm", conversation_id="room"
        )


class ActionTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_teleport_does_not_hold_chat_or_interactions(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def teleport(*args):
            started.set()
            await release.wait()

        bot = SimpleNamespace(
            highrise=SimpleNamespace(
                teleport=teleport,
                chat=AsyncMock(),
                send_whisper=AsyncMock(),
                send_emote=AsyncMock(),
                react=AsyncMock(),
            ),
        )
        actions = sdk.ThrottledActions(bot, interaction_rate=10)
        actions.start()
        try:
            await actions.teleport("one", sdk.Position(1, 2, 3))
            await asyncio.wait_for(started.wait(), 1)
            await actions.chat("hello")
            await actions.whisper("one", "greetings")
            self.assertTrue(await actions.emote("emote-hello", "one"))
            self.assertTrue(await actions.react("heart", "one"))
            await asyncio.sleep(0)
            bot.highrise.chat.assert_awaited_once_with("hello")
            bot.highrise.send_whisper.assert_awaited_once_with("one", "greetings")
            bot.highrise.send_emote.assert_awaited_once_with("emote-hello", "one")
            bot.highrise.react.assert_awaited_once_with("heart", "one")
            release.set()
            await asyncio.wait_for(actions.flush(), 1)
            self.assertEqual(actions.stats(), {"queued": 0, "sent": 5, "failed": 0, "dropped": 0})
        finally:
            await actions.stop()

    async def test_stop_clears_pending_work_and_new_connection_starts_empty(self):
        active = asyncio.Event()

        async def send(message):
            active.set()
            await asyncio.Future()

        bot = SimpleNamespace(highrise=SimpleNamespace(chat=send))
        actions = sdk.ThrottledActions(bot, queue_size=1)
        actions.start()
        await actions.chat("in progress")
        await asyncio.wait_for(active.wait(), 1)
        await actions.chat("queued")
        self.assertFalse(await actions.emote("rejected"))
        await asyncio.wait_for(actions.stop(), 1)
        self.assertEqual(actions.stats(), {"queued": 0, "sent": 0, "failed": 0, "dropped": 3})
        bot.highrise = SimpleNamespace(chat=AsyncMock())
        actions.start()
        try:
            await actions.chat("fresh")
            await asyncio.wait_for(actions.flush(), 1)
            bot.highrise.chat.assert_awaited_once_with("fresh")
        finally:
            await actions.stop()


class RosterAndChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_roster_waiters_wake_on_membership_changes_only(self):
        tracker = sdk.RoomTracker()
        player = sdk.User("one", "Alice")
        tracker.add(player)
        revision = tracker.roster_revision
        waiter = asyncio.create_task(tracker.wait_for_roster_change(revision, timeout=1))
        await asyncio.sleep(0)
        tracker.move(player.id, sdk.Position(1, 0, 2))
        tracker.replace_roster([(player, sdk.Position(6, 0, 7))])
        await asyncio.sleep(0)
        self.assertFalse(waiter.done())
        self.assertEqual(tracker.get_user_id(" aLiCe "), "one")
        tracker.replace_roster([(sdk.User("two", "Bob"), None)])
        self.assertEqual(await waiter, revision + 1)
        self.assertEqual(await tracker.wait_for_roster_change(revision), revision + 1)
        self.assertEqual(tracker.usernames, {"two": "Bob"})

    async def test_chunk_order_and_actual_footer_size(self):
        chunks = sdk.chunk_for_chat("short\n" + "abcdefghij" * 3, limit=12, prefix=">")
        self.assertEqual(chunks[0], ">short")
        self.assertEqual("".join(chunk[1:] for chunk in chunks[1:]), "abcdefghij" * 3)
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))
        room = SimpleNamespace(chat=AsyncMock())
        await sdk.send_long_message(room, "x" * 1000, limit=20, delay=0)
        self.assertGreater(room.chat.await_count, 10)
        self.assertTrue(all(len(call.args[0]) <= 20 for call in room.chat.await_args_list))
        room.chat.reset_mock()
        await sdk.send_long_message(room, "1234567890", limit=5, delay=0)
        self.assertEqual([call.args[0] for call in room.chat.await_args_list], ["12345", "67890"])


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_typed_cache_keys_and_per_function_storage(self):
        decorator = sdk.cached()

        @decorator
        def same(value):
            return type(value).__name__

        other = decorator(lambda value: "other")
        self.assertEqual(same([1]), "list")
        self.assertEqual(same((1,)), "tuple")
        self.assertEqual(same(True), "bool")
        self.assertEqual(same(1), "int")
        self.assertEqual(other([1]), "other")

    async def test_async_cache_shares_result_when_one_caller_cancels(self):
        gate = asyncio.Event()
        started = asyncio.Event()
        executions = 0

        @sdk.async_cached()
        async def read(options):
            nonlocal executions
            executions += 1
            started.set()
            await gate.wait()
            return executions

        first = asyncio.create_task(read({"a": 1, "b": 2}))
        await asyncio.wait_for(started.wait(), 1)
        second = asyncio.create_task(read({"b": 2, "a": 1}))
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        gate.set()
        self.assertEqual(await second, 1)
        self.assertEqual(await read({"a": 1, "b": 2}), 1)
        read.cache_clear()
        self.assertEqual(await read({"a": 1, "b": 2}), 2)

    async def test_raw_web_client_shares_equivalent_queries(self):
        calls = 0

        async def serve(request):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return web.json_response(dict(request.query))

        app = web.Application()
        app.router.add_get("/items", serve)
        async with TestServer(app) as server:
            async with sdk.CachedWebAPI(str(server.make_url("/")), timeout=1) as api:
                results = await asyncio.gather(
                    api.get("/items", params={"a": "1", "b": "2"}),
                    api.get("/items", params={"b": "2", "a": "1"}),
                )
                self.assertEqual(calls, 1)
                self.assertEqual(results, [{"a": "1", "b": "2"}] * 2)
                api.invalidate_cache()
                await api.get("/items", params={"a": "1", "b": "2"})
                self.assertEqual(calls, 2)
