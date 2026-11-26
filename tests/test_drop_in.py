"""Compatibility checks for bots using the standard Highrise imports and launcher."""

import asyncio
import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import highrise
from aiohttp import web
from aiohttp.test_utils import TestServer
from highrise.models import (
    AnchorHitRequest,
    AnchorPosition,
    ChannelRequest,
    GetWalletRequest,
)
from highrise.models_control import ControlEvent, InstanceStartedEvent
from highrise.models_control import converter as control_converter
from highrise.models_webapi import GetPublicItemResponse, Item
from highrise.webapi import WebAPI


class PublicInterfaceTests(unittest.TestCase):
    def test_converter_round_trips_requests_with_nested_models(self):
        channel = ChannelRequest("hello", {"staff"}, {"reader"}, "7")
        body = json.loads(highrise.converter.dumps(channel, highrise.Outgoing))
        self.assertEqual(
            body,
            {
                "_type": "ChannelRequest",
                "message": "hello",
                "tags": ["staff"],
                "only_to": ["reader"],
                "rid": "7",
            },
        )
        self.assertEqual(highrise.converter.structure(body, highrise.Outgoing), channel)
        self.assertEqual(ChannelRequest("next").tags, set())
        anchor = AnchorHitRequest(AnchorPosition("seat", 2))
        self.assertEqual(
            highrise.converter.loads(
                highrise.converter.dumps(anchor, highrise.Outgoing), highrise.Outgoing
            ),
            anchor,
        )

    def test_control_converter_returns_expected_event(self):
        event = control_converter.loads(
            '{"_type":"InstanceStartedEvent","instance_id":"one"}', ControlEvent
        )
        self.assertEqual(event, InstanceStartedEvent("one"))


class DropInRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_low_level_request_uses_runtime_correlation(self):
        sent = []

        class Socket:
            async def send_str(self, frame):
                body = json.loads(frame)
                sent.append(body)
                hr._resolve_pending(
                    body["rid"],
                    {
                        "_type": "GetWalletResponse",
                        "rid": body["rid"],
                        "content": [{"type": "gold", "amount": 5}],
                    },
                )

        hr = highrise.Highrise(Socket())
        request = GetWalletRequest()
        reply = await highrise.do_req_resp(hr, request)
        self.assertIsInstance(reply, GetWalletRequest.GetWalletResponse)
        self.assertEqual(reply.content[0].amount, 5)
        self.assertEqual(sent, [{"_type": "GetWalletRequest", "rid": request.rid}])
        self.assertEqual(hr._pending, {})

    async def test_webapi_preserves_types_and_accepts_current_item_payloads(self):
        requests = []

        async def serve(request):
            requests.append(request.path)
            return web.json_response(
                {
                    "item": {
                        "item_id": "hat",
                        "item_name": "Hat",
                    "new_server_field": "retained",
                        "category": "future_category",
                        "m_front_skin_part_list": [
                            {
                                "imageFile": "hat.png",
                                "attachmentName": "head",
                                "hasRemoteRenderLayer": True,
                            }
                        ],
                        "created_at": "2026-01-01T00:00:00Z",
                    },
                    "related_items": None,
                    "storefront_listings": None,
                }
            )

        class RecordingAPI(WebAPI):
            async def send_request(self, endpoint, cl=None):
                self.model_requested = cl
                return await super().send_request(endpoint, cl)

        app = web.Application()
        app.router.add_get("/items/hat", serve)
        async with (
            TestServer(app) as server,
            RecordingAPI(str(server.make_url("/"))) as api,
        ):
            first, second = await asyncio.gather(api.get_item("hat"), api.get_item("hat"))
            self.assertIs(api.model_requested, GetPublicItemResponse)
            self.assertIs(first, second)
            self.assertIsInstance(first.item, Item)
            self.assertEqual(first.item.category.value, "future_category")
            self.assertEqual(first.item.created_at.format("YYYY"), "2026")
            skin = first.item.m_front_skin_part_list[0]
            self.assertEqual((skin.image_file, skin.attachment_name), ("hat.png", "head"))
            self.assertTrue(skin.has_remote_render_layer)
            raw = await api.send_request("/items/hat", dict)
            self.assertEqual(raw["item"]["item_id"], "hat")
            self.assertEqual(raw["item"]["new_server_field"], "retained")
        self.assertEqual(requests, ["/items/hat"])

    async def test_standard_cli_runs_unchanged_bot_on_each_connection(self):
        sessions = 0
        started = []

        async def serve(request):
            nonlocal sessions
            sessions += 1
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json(
                {
                    "_type": "SessionMetadata",
                    "user_id": "bot",
                    "connection_id": str(sessions),
                    "room_info": {"owner_id": "owner", "room_name": "Test"},
                    "rate_limits": {"chat": [3, 2.0]},
                }
            )
            async for frame in ws:
                call = json.loads(frame.data)
                if call["_type"] == "GetRoomUsersRequest":
                    await ws.send_json(
                        {
                            "_type": "GetRoomUsersResponse",
                            "content": [],
                            "rid": call["rid"],
                        }
                    )
                elif call["_type"] == "ChatRequest":
                    await ws.send_json(
                        {
                            "_type": "Error",
                            "message": "rejected by test",
                            "rid": call["rid"],
                        }
                    )
                elif call["_type"] == "ReactionRequest":
                    started.append(sessions)
                    await ws.send_json({"_type": "ReactionResponse", "rid": call["rid"]})
                    if sessions == 2:
                        await ws.send_json(
                            {
                                "_type": "Error",
                                "message": "done",
                                "do_not_reconnect": True,
                            }
                        )
                    await ws.close()
            return ws

        app = web.Application()
        app.router.add_get("/bot", serve)
        launcher = """
            from highrise import BaseBot, ResponseError
            from highrise.models import SessionMetadata
            from highrise.webapi import WebAPI

            class Bot(BaseBot):
                async def on_start(self, metadata: SessionMetadata):
                    assert isinstance(metadata, SessionMetadata)
                    assert metadata.rate_limits['chat'] == (3, 2.0)
                    assert isinstance(self.webapi, WebAPI)
                    try:
                        await self.highrise.chat("hello")
                    except ResponseError as error:
                        assert str(error) == "rejected by test"
                        await self.highrise.react("wave", "player")
        """
        async with TestServer(app) as server:
            with tempfile.TemporaryDirectory() as directory:
                Path(directory, "existing_bot.py").write_text(textwrap.dedent(launcher))
                root = str(Path(highrise.__file__).resolve().parents[1])
                python_path = os.pathsep.join(
                    path for path in (root, os.environ.get("PYTHONPATH")) if path
                )
                env = {
                    **os.environ,
                    "PYTHONPATH": python_path,
                    "HR_BOTAPI_URL": str(server.make_url("/bot")).replace("http:", "ws:", 1),
                    "HR_FAST_FIRE_AND_FORGET": "0",
                }
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "highrise",
                    "existing_bot:Bot",
                    "room",
                    "test-token",
                    cwd=directory,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), 8)
                finally:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
        self.assertEqual(process.returncode, 0, (stdout + stderr).decode())
        self.assertEqual(started, [1, 2], (stdout + stderr).decode())
