"""Regression tests for connection-aware bot helpers."""

import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import highrise
import highrise_fast as sdk
from aiohttp import web
from aiohttp.test_utils import TestServer


class AwaiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_expect_filters_and_releases_capacity_immediately(self):
        awaiter = sdk.Awaiter(max_pending=2)

        def broken(*args):
            raise ValueError("broken predicate")

        failed = awaiter.expect("chat", predicate=broken)
        expected = awaiter.expect("chat", predicate=lambda uid, text: text == "yes")
        self.assertEqual(awaiter.emit("chat", "player", "no"), 0)
        with self.assertRaisesRegex(ValueError, "broken predicate"):
            await failed
        self.assertEqual(awaiter.emit("chat", "player", "yes"), 1)
        self.assertEqual(await expected, ("player", "yes"))
        self.assertEqual(awaiter.pending_count, 0)
        self.assertIsNone(await awaiter.wait_for("chat", timeout=0))

    async def test_collect_and_wait_any(self):
        awaiter = sdk.Awaiter()
        collected = asyncio.create_task(
            awaiter.collect("reaction", count=3, unique_by=lambda uid, _: uid, timeout=0.02)
        )
        first = asyncio.create_task(
            awaiter.wait_any("chat", "reaction", predicate=lambda event, *_: event == "reaction")
        )
        await asyncio.sleep(0)
        awaiter.emit("chat", "one", "hello")
        awaiter.emit("reaction", "one", "heart")
        awaiter.emit("reaction", "one", "thumbs")
        awaiter.emit("reaction", "two", "heart")
        self.assertEqual(await first, ("reaction", ("one", "heart")))
        self.assertEqual(await collected, [("one", "heart"), ("two", "heart")])
        self.assertEqual(awaiter.pending_count, 0)

    async def test_cancel_from_predicate_and_skip_buffered_replays(self):
        bot = sdk.BaseBot(track_room=False)
        awaiter = bot.awaiter

        def cancel(*args):
            awaiter.cancel_all()
            return True

        abandoned = awaiter.expect("chat", predicate=cancel)
        self.assertEqual(awaiter.emit("chat", "player", "hi"), 0)
        self.assertTrue(abandoned.cancelled())

        chat = {"user": {"id": "player", "username": "Player"}, "message": "hi"}
        first = awaiter.expect("chat")
        async with sdk.TaskGroup() as group:
            with patch.object(sdk, "_dispatch_backpressure_check", side_effect=(True, False)):
                try:
                    sdk._dispatch_event(bot, "bot", "ChatEvent", chat, group)
                    second = awaiter.expect("chat")
                    sdk._dispatch_event(bot, "bot", "ChatEvent", chat, group, buffered=True)
                    self.assertFalse(second.done())
                finally:
                    sdk._discard_buffered_chat(group)
        self.assertEqual((await first)[1], "hi")
        awaiter.cancel_all()
        self.assertTrue(second.cancelled())

    async def test_live_subscriptions_hooks_and_disconnect_cleanup(self):
        listening = asyncio.Event()
        handled = asyncio.Event()
        finished = asyncio.Event()

        class Bot(highrise.BaseBot):
            def __init__(self):
                super().__init__(track_room=False, await_events=("reaction", "whisper"))

            async def on_start(self, metadata):
                reaction = self.awaiter.expect("reaction", timeout=1)
                whisper = self.awaiter.expect("whisper", timeout=1)
                self.pending = self.awaiter.expect("chat")
                listening.set()
                self.seen = await asyncio.gather(reaction, whisper)
                finished.set()

            async def on_reaction(self, user, reaction, receiver):
                self.hook = (user, reaction, receiver)
                handled.set()

        subscriptions = []

        async def serve(request):
            subscriptions.append(request.query["events"])
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json(
                {
                    "_type": "SessionMetadata",
                    "user_id": "bot",
                    "room_info": {"owner_id": "owner", "room_name": "Test Room"},
                }
            )
            await listening.wait()
            player = {"id": "player", "username": "Player"}
            await ws.send_json(
                {
                    "_type": "ReactionEvent",
                    "user": player,
                    "receiver": {"id": "bot", "username": "Bot"},
                    "reaction": "heart",
                }
            )
            await ws.send_json(
                {
                    "_type": "ChatEvent",
                    "user": player,
                    "message": "hi",
                    "whisper": True,
                }
            )
            await asyncio.wait_for(asyncio.gather(handled.wait(), finished.wait()), 1)
            await ws.send_json({"_type": "Error", "message": "done", "do_not_reconnect": True})
            await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/bot", serve)
        bot = Bot()
        async with TestServer(app) as server:
            url = str(server.make_url("/bot")).replace("http:", "ws:", 1)
            with patch.object(sdk, "BASE_WS_URL", url):
                await asyncio.wait_for(bot.login("room", "token"), 3)
        self.assertEqual(subscriptions, ["chat,reaction"])
        reaction, whisper = bot.seen
        self.assertEqual(reaction, bot.hook)
        self.assertEqual((reaction[0].id, reaction[1], reaction[2].id), ("player", "heart", "bot"))
        self.assertEqual((whisper[0].username, whisper[1]), ("Player", "hi"))
        self.assertTrue(bot.pending.cancelled())
        self.assertEqual(bot.awaiter.pending_count, 0)

    async def test_each_supported_event_matches_the_public_hook_arguments(self):
        name_map = {
            "chat": ("ChatEvent", 2),
            "whisper": ("ChatEvent", 2),
            "emote": ("EmoteEvent", 3),
            "reaction": ("ReactionEvent", 3),
            "user_join": ("UserJoinedEvent", 2),
            "user_leave": ("UserLeftEvent", 1),
            "user_move": ("UserMovedEvent", 2),
            "tip": ("TipReactionEvent", 3),
            "channel": ("ChannelEvent", 3),
            "voice": ("VoiceEvent", 2),
            "message": ("MessageEvent", 3),
            "moderation": ("RoomModeratedEvent", 4),
        }
        bot = sdk.BaseBot(track_room=False, await_events=name_map)
        subscriptions = sdk.active_subscriptions(bot)
        self.assertEqual(subscriptions, set(sdk._EVENT_TO_SUBSCRIPTION.values()))
        async with sdk.TaskGroup() as group:
            for name, (packet_type, argument_count) in name_map.items():
                with self.subTest(name=name):
                    pending = bot.awaiter.expect(name, timeout=0)
                    packet = dict(sdk.BASE_PAYLOADS[packet_type])
                    if name == "whisper":
                        packet["whisper"] = True
                    self.assertTrue(
                        sdk._dispatch_event(bot, "bot", packet_type, packet, group, subscriptions)
                    )
                    result = await pending
                    self.assertIsNotNone(result)
                    self.assertEqual(len(result), argument_count)


class StateTests(unittest.IsolatedAsyncioTestCase):
    async def test_atomic_store_preserves_previous_state_on_failed_write(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "time.json"
            store = sdk.AtomicJsonStore(path)
            self.assertEqual(await store.load(default={}), {})
            original = {"Québec": 1}
            await store.save(original)
            with self.assertRaises(ValueError):
                await store.save({"invalid": float("nan")})
            self.assertEqual(await store.load(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

    async def test_role_store_persistence_and_command_permissions(self):
        with TemporaryDirectory() as directory:
            file = sdk.AtomicJsonStore(Path(directory) / "roles.json")
            roles = sdk.RoleStore(file, hierarchy=("mod", "owner"))
            roles.grant("owner", "Owner")
            roles.grant("mod", "mod")
            await roles.save()
            restored = sdk.RoleStore(file, hierarchy=("mod", "owner"))
            await restored.load()
            registry = sdk.CommandRegistry()
            registry.set_permission_checker(restored.permission_checker)
            called = AsyncMock()
            bot = SimpleNamespace(highrise=SimpleNamespace(send_whisper=AsyncMock()))

            @registry.command("manage", rank="owner")
            async def manage(ctx):
                await called()

            for uid in ("mod", "owner"):
                await registry.handle(
                    bot, sdk.User(id=uid, username=uid), "!manage", source="whisper"
                )
            called.assert_awaited_once()
            self.assertTrue(restored.allows("owner", "mod"))
            self.assertTrue(restored.revoke("mod", "MOD"))
            self.assertFalse(restored.allows("mod", "mod"))

            await file.save({"invalid": [1]})
            with self.assertRaises(ValueError):
                await restored.load()
            self.assertEqual(restored.roles_for("owner"), {"owner"})

    async def test_presence_handles_missed_leave_and_reloads_checkpoint(self):
        now = 0.0

        def clock():
            return now

        timer = sdk.PresenceTimer(
            {"a": 5}, exclude_ids={"bot"}, exclude_usernames={"R0_.YA__"}, clock=clock
        )
        timer.observe({"a": "Player", "b": "Other", "bot": "Bot", "excluded": "r0_.ya__"})
        now = 7.0
        timer.observe({"b": "Renamed"})
        now = 8.0
        self.assertEqual(timer.leaderboard(), [("a", 12.0), ("b", 8.0)])
        restored = sdk.PresenceTimer(timer.snapshot(), clock=clock)
        restored.observe({"a": "Player"})
        now = 10.0
        restored.pause()
        now = 100.0
        self.assertEqual(restored.seconds("a"), 14.0)
        restored.observe({"a": "Player"})
        restored.reset()
        now = 101.0
        self.assertEqual(restored.snapshot(), {"a": 1.0})

    async def test_occupancy_requires_confirmed_empty_then_fires_once(self):
        now = 0.0

        def clock():
            return now

        detector = sdk.RoomOccupancyTrigger(
            5, exclude_ids={"bot"}, exclude_usernames={"R0_.YA__", "__R0_Sa"}, clock=clock
        )
        empty = {"bot": "Bot", "ignored": "__r0_sa"}
        occupied = {"a": "Player", **empty}
        self.assertFalse(detector.observe(empty))
        now = 8.0
        self.assertFalse(detector.observe(occupied))
        self.assertFalse(detector.observe(empty))
        now = 14.0
        self.assertFalse(detector.observe(empty))
        self.assertTrue(detector.armed)
        self.assertTrue(detector.observe(occupied))
        self.assertFalse(detector.observe(occupied))
        detector.observe(empty)
        now = 20.0
        detector.observe(empty)
        detector.reset()
        self.assertFalse(detector.observe(occupied))


class JobAndActionTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_skips_overruns_pauses_and_deduplicates_start(self):
        first = asyncio.Event()
        release = asyncio.Event()
        second = asyncio.Event()
        runs = 0

        async def work():
            nonlocal runs
            runs += 1
            if runs == 1:
                first.set()
                await release.wait()
            else:
                second.set()

        job = sdk.PeriodicJob(0.01, work)
        manager = sdk.TaskManager()
        try:
            task = job.start(manager)
            self.assertIs(job.start(manager), task)
            await asyncio.wait_for(first.wait(), 1)
            job.pause()
            await asyncio.sleep(0.025)
            self.assertEqual(runs, 1)
            release.set()
            await asyncio.sleep(0.02)
            self.assertEqual(runs, 1)
            self.assertGreaterEqual(job.missed_ticks, 2)
            job.resume()
            await asyncio.wait_for(second.wait(), 1)
            await job.stop()
            self.assertTrue(task.cancelled())
        finally:
            await manager.close()

    async def test_retry_policy_and_change_detector(self):
        retry = sdk.RetryPolicy(attempts=3, delay=0)
        flaky = AsyncMock(side_effect=[OSError(), asyncio.TimeoutError(), "ok"])
        self.assertEqual(await retry.run(flaky), "ok")
        self.assertEqual(flaky.await_count, 3)
        bad = AsyncMock(side_effect=ValueError("permanent"))
        with self.assertRaisesRegex(ValueError, "permanent"):
            await retry.run(bad)
        bad.assert_awaited_once()

        username = sdk.ChangeDetector(key=str.casefold, emit_initial=False)
        self.assertFalse(username.update("Player"))
        self.assertFalse(username.update("PLAYER"))
        self.assertTrue(username.update("Renamed"))

    async def test_cancel_waiting_and_queued_interactions_without_sending_them(self):
        send = AsyncMock()
        bot = SimpleNamespace(highrise=SimpleNamespace(send_emote=send))
        actions = sdk.ThrottledActions(bot, queue_size=3)
        waiting = asyncio.Event()
        release = asyncio.Event()

        async def acquire():
            waiting.set()
            await release.wait()

        actions.start()
        try:
            with patch.object(actions._buckets["interaction"], "acquire", acquire):
                await actions.emote("old", "u1", key="u1")
                await asyncio.wait_for(waiting.wait(), 1)
                await actions.emote("old-again", "u1", key="u1")
                await actions.emote("fresh", "u2", key="u2")
                self.assertEqual(actions.cancel_pending("u1"), 2)
                self.assertEqual(actions.cancel_pending("u1"), 0)
                self.assertTrue(await actions.emote("expired", "u2", expires_in=0))
                release.set()
                await asyncio.wait_for(actions.flush(), 1)
        finally:
            await actions.stop()
        send.assert_awaited_once_with("fresh", "u2")
        self.assertEqual(actions.stats(), {"queued": 0, "sent": 1, "failed": 0, "dropped": 3})
