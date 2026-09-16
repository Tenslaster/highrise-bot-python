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
DEFAULT_OUTFIT = [OutfitItem(type="clothing", amount=1, id="body-flesh", account_bound=False, active_palette=0)]
