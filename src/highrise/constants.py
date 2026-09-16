from .models.websocket.highrise_models import OutfitItem

WEBSOCKET_EVENTS = [
    "SessionMetadata", "ChatEvent", "ReactionEvent", "UserMovedEvent",
    "UserJoinedEvent", "UserLeftEvent", "MessageEvent", "TipReactionEvent",
    "RoomModeratedEvent", "ChannelEvent", "EmoteEvent", "VoiceEvent",
]

EVENT_HOOK_MAP: dict[str, tuple[str, ...]] = {
    "ChatEvent": ("on_chat", "on_whisper"),
    "UserJoinedEvent": ("on_user_join",),
    "UserLeftEvent": ("on_user_leave",),
    "UserMovedEvent": ("on_user_move",),
    "EmoteEvent": ("on_emote",),
    "ReactionEvent": ("on_reaction",),
    "TipReactionEvent": ("on_tip",),
    "MessageEvent": ("on_message",),
    "VoiceEvent": ("on_voice_change",),
    "RoomModeratedEvent": ("on_moderate",),
    "ChannelEvent": ("on_channel",),
}

FACING_DIRECTIONS = frozenset({"FrontRight", "FrontLeft", "BackRight", "BackLeft"})
HIGHRISE_WS_URI = "wss://highrise.game/web/botapi"
WEBAPI_BASE_URL = "https://webapi.highrise.game"
HIGHRISE_CLOUDFLARE_URL = "https://d4v5j9dz6t9fz.cloudfront.net/"
SERVER_ERRORS = frozenset({
    "Bots must have designer rights or be invited to enter a room.",
    "Invalid room id", "API token not found",
})

# Full default outfit retained for backwards compatibility.
DEFAULT_OUTFIT = [
    OutfitItem("clothing", 1, "body-flesh", False, 0),
    OutfitItem("clothing", 1, "eye-f_09b", False, 31),
    OutfitItem("clothing", 1, "eyebrow-n_08", True, 79),
    OutfitItem("clothing", 1, "hair_front-n_basic2020overshoulderwavyshort", True, 23),
    OutfitItem("clothing", 1, "hair_back-n_basic2020overshoulderwavyshort", True, 23),
    OutfitItem("clothing", 1, "mouth-basic2018downturnedthinpeaked", True, 1),
    OutfitItem("clothing", 1, "freckle-n_basic2018freckle22", True, 0),
    OutfitItem("clothing", 1, "freckle-n_friendlymonstersmarchskypass2022friendlyblush", True, 0),
    OutfitItem("clothing", 1, "freckle-n_basic2018freckle21", True, 0),
    OutfitItem("clothing", 1, "dress-f_strapless_beige", False, 0),
    OutfitItem("clothing", 1, "shoes-n_starteritems2019flatswhite", True, 0),
    OutfitItem("clothing", 1, "pants-n_underwearstore2021blackspeedo", True, 0),
    OutfitItem("clothing", 1, "nose-n_01", True, 0),
]
