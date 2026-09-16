from highrise.models.websocket.requests import EmoteRequest


def test_room_emote_payload_omits_target():
    assert EmoteRequest("dance-macarena").to_dict() == {
        "_type": "EmoteRequest",
        "emote_id": "dance-macarena",
    }


def test_targeted_emote_payload_includes_target():
    assert EmoteRequest("dance-macarena", "68fc8fc4750fa63a09662090").to_dict() == {
        "_type": "EmoteRequest",
        "emote_id": "dance-macarena",
        "target_user_id": "68fc8fc4750fa63a09662090",
    }
