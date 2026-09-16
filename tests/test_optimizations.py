import pytest
from highrise.models.websocket.highrise_models import Position, Message, User
from highrise.cache.room_users import RoomUsersCache
from highrise.tools.utils import Utils
from highrise.models.websocket.requests import FloorHitRequest, ChatRequest, TeleportRequest

def test_position_distance_hypot():
    p1 = Position(0.0, 0.0, 0.0)
    p2 = Position(3.0, 4.0, 0.0)
    assert p1.distance_to(p2) == 5.0

    p3 = Position(1.0, 2.0, 2.0)
    p4 = Position(1.0, 2.0, 2.0)
    assert p3.distance_to(p4) == 0.0

def test_message_lazy_parsing_and_zero_alloc_args():
    msg = Message("!give @alice 100 gold")
    assert msg.command() == "!give"
    assert msg.args() == ["@alice", "100", "gold"]
    # Direct index without slicing
    assert msg.args(0) == "@alice"
    assert msg.args(1) == "100"
    assert msg.args(2) == "gold"
    assert msg.args(3) is None
    # Python-compatible negative indexing without slicing
    assert msg.args(-1) == "gold"
    assert msg.args(-2) == "100"
    assert msg.args(-3) == "@alice"
    assert msg.args(-4) is None
    assert msg.args(99) is None

    # Mentions cached
    assert msg.mentions() == ["alice"]
    assert msg.mentions(0) == "alice"
    assert msg.mentions(-1) == "alice"
    assert msg.mentions(1) is None
    assert msg.mentions(-2) is None

def test_message_empty_content():
    msg = Message("")
    assert msg.command() is None
    assert msg.args() == []
    assert msg.args(0) is None
    assert msg.mentions() == []
    assert msg.mentions(0) is None

def test_utils_split_tip_fast():
    assert Utils.split_tip(0) == []
    assert Utils.split_tip(-10) == []
    # 10565: 10000 + 500 + 50 + 10 + 5
    splits = Utils.split_tip(10565)
    assert splits == ["gold_bar_10k", "gold_bar_500", "gold_bar_50", "gold_bar_10", "gold_bar_5"]

def test_room_users_cache_pythonic_interface():
    cache = RoomUsersCache()
    u1 = User("u1", "alice")
    p1 = Position(1.0, 2.0, 3.0)
    cache._add(u1, p1)

    assert len(cache) == 1
    assert "u1" in cache
    assert "alice" in cache
    assert "bob" not in cache
    assert cache.get_user("u1") == u1
    assert cache.get_user("alice") == u1
    assert cache.get_user("unknown") is None

    items = list(cache)
    assert len(items) == 1
    assert items[0] == (u1, p1)

def test_requests_dict_generation():
    req = FloorHitRequest(Position(1.0, 2.0, 3.0, "BackLeft"))
    d = req.to_dict()
    assert d == {
        "_type": "FloorHitRequest",
        "destination": {"x": 1.0, "y": 2.0, "z": 3.0, "facing": "BackLeft"}
    }
