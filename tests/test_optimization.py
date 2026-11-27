"""Regression coverage for room tracking, dispatch, persistence, and Web API reads."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import highrise_fast as sdk
from aiohttp import web
from aiohttp.test_utils import TestServer


class RoomTrackerTests(unittest.TestCase):
    def test_movement_anchor_and_roster_replacement(self):
        tracker = sdk.RoomTracker()
        user = sdk.User("one", "Alice")
        other = sdk.User("two", "Bob")
        tracker.replace_roster([(user, sdk.Position(1, 0, 1)), (other, sdk.Position(20, 0, 20))])
        tracker.move(user.id, sdk.Position(2, 0, 3))
        self.assertEqual(tracker.get_nearby(2, 3, 0), [user.id])
        self.assertEqual(tracker.get_username(user.id), "Alice")
        self.assertCountEqual(tracker.get_nearby(0, 0, 4000), [user.id, other.id])
        tracker.move(user.id, sdk.AnchorPosition("seat", 0))
        self.assertIsNone(tracker.get_position(user.id))
        self.assertEqual(tracker.get_anchor(user.id), ("seat", 0))
        self.assertEqual(tracker.get_nearby(0, 0, 4000), [other.id])
        tracker.replace_roster([(user, sdk.Position(-5, 0, -5))])
        self.assertEqual(tracker.usernames, {"one": "Alice"})
        self.assertIsNone(tracker.get_anchor(user.id))
        tracker.remove(user.id)
        self.assertEqual(tracker.get_nearby(0, 0, 4000), [])

    def test_tracking_can_be_disabled(self):
        bot = sdk.BaseBot(track_room=False)
        self.assertIsNone(bot.room_tracker)
        self.assertNotIn("user_moved", sdk.active_subscriptions(bot))
        bot.on_user_move = AsyncMock()
        self.assertIn("user_moved", sdk.active_subscriptions(bot))


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_tracker_updates_without_spawning_default_hook(self):
        bot = sdk.BaseBot()
        payload = {
            "user": {"id": "one", "username": "Alice"},
            "position": {"x": 1.0, "y": 0.0, "z": 2.0},
        }
        with patch.object(sdk, "_spawn_task") as spawn:
            self.assertTrue(sdk._dispatch_event(bot, "bot", "UserMovedEvent", payload, None))
        spawn.assert_not_called()
        self.assertEqual(bot.room_tracker.get_position("one"), (1.0, 0.0, 2.0))

        async with sdk.TaskGroup() as group:
            bot.on_user_move = AsyncMock()
            sdk._dispatch_event(bot, "bot", "UserMovedEvent", payload, group)
        bot.on_user_move.assert_awaited_once()

    async def test_chat_queue_resumes_in_order_when_handler_slot_opens(self):
        gate = asyncio.Event()
        delivered = asyncio.Event()
        handled = []

        class Bot(sdk.BaseBot):
            async def on_chat(self, user, message):
                handled.append(message)
                if len(handled) == 2:
                    delivered.set()

        bot = Bot()
        sdk.reset_stats()
        sdk.start_chat_drain_task()
        try:
            with patch.object(sdk, "_DISPATCH_MAX_CONCURRENCY", 1):
                async with sdk.TaskGroup() as group:
                    sdk._spawn_task(group, gate.wait())
                    self.assertEqual(sdk.stats()["dispatch_active"], 1)
                    sdk.reset_stats()
                    self.assertEqual(sdk.stats()["dispatch_active"], 1)
                    for message in ("first", "second"):
                        payload = {"user": {"id": "one", "username": "Alice"}, "message": message}
                        sdk._dispatch_event(bot, "bot", "ChatEvent", payload, group)
                    self.assertEqual(sdk.stats()["dispatch_queued"], 2)
                    gate.set()
                    await asyncio.wait_for(delivered.wait(), 1)
            self.assertEqual(handled, ["first", "second"])
            self.assertEqual(sdk.stats()["dispatch_queued"], 0)
        finally:
            await sdk.stop_chat_drain_task()
            sdk.reset_stats()


class PersistentWriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_arriving_during_save_is_flushed_without_overlap(self):
        started = asyncio.Event()
        release = asyncio.Event()
        saved = []

        async def save(data):
            if data == 1:
                started.set()
                await release.wait()
            saved.append(data)

        saver = sdk.DebouncedSaver(save, delay=0)
        saver.trigger(1)
        await asyncio.wait_for(started.wait(), 1)
        saver.trigger(2)
        saver.trigger(3)
        stopping = asyncio.create_task(saver.stop())
        await asyncio.sleep(0)
        self.assertFalse(stopping.done())
        release.set()
        await asyncio.wait_for(stopping, 1)
        self.assertEqual(saved, [1, 3])


class WebReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_size_and_counters(self):
        calls = 0

        async def serve(request):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.02)
            return web.json_response({"ok": True})

        app = web.Application()
        app.router.add_get("/{endpoint}", serve)
        async with TestServer(app) as server:
            async with sdk.WebAPI(str(server.make_url("/")), cache_size=1) as api:
                await asyncio.gather(*(api.send_request("/first") for _ in range(5)))
                await api.send_request("/first")
                await api.send_request("/second")
                await api.send_request("/first")
                self.assertEqual(
                    api.cache_info(),
                    {
                        "hits": 1,
                        "misses": 7,
                        "coalesced": 4,
                        "http_requests": 3,
                        "entries": 1,
                        "inflight": 0,
                    },
                )
                self.assertEqual(calls, 3)

    async def test_iterator_limits_requests_and_stops_on_repeated_cursor(self):
        async with sdk.WebAPI() as api:
            pages = [
                sdk.GetPublicItemsResponse(
                    {"items": [{"item_id": "1"}, {"item_id": "2"}], "last_id": "2"}
                ),
                sdk.GetPublicItemsResponse({"items": [{"item_id": "3"}], "last_id": "3"}),
                sdk.GetPublicItemsResponse({"items": [{"item_id": "3"}], "last_id": "3"}),
            ]
            with patch.object(api, "get_items", side_effect=pages) as fetch:
                items = [item.item_id async for item in api.iter_items(page_size=2, category="hat")]
                self.assertEqual(items, ["1", "2", "3"])
                self.assertEqual(
                    [call.kwargs["starts_after"] for call in fetch.call_args_list], [None, "2", "3"]
                )
                self.assertTrue(
                    all(call.kwargs["category"] == "hat" for call in fetch.call_args_list)
                )
            with patch.object(api, "get_items", return_value=pages[0]) as fetch:
                items = [item.item_id async for item in api.iter_items(page_size=20, max_items=1)]
                self.assertEqual(items, ["1"])
                fetch.assert_awaited_once_with(starts_after=None, limit=1)
