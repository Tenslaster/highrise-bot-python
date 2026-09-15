from .models.websocket.highrise_models import OutfitItem

WEBSOCKET_EVENTS = [
    'SessionMetadata', 'ChatEvent', 'UserMovedEvent', 
    'UserJoinedEvent', 'UserLeftEvent','MessageEvent', 
    'TipReactionEvent', 'RoomModeratedEvent', 'ChannelEvent',
    'EmoteEvent', 'VoiceEvent'
]

EVENT_HOOK_MAP: dict[str, tuple[str, ...]] = {
    "ChatEvent": ("on_chat", "on_whisper"),
    "UserJoinedEvent": ("on_user_join",),
    "UserLeftEvent": ("on_user_leave",),
    "UserMovedEvent": ("on_user_move",),
    "EmoteEvent": ("on_emote",),
    "TipReactionEvent": ("on_tip",),
    "MessageEvent": ("on_message",),
    "VoiceEvent": ("on_voice_change",),
    "RoomModeratedEvent": ("on_moderate",),
    "ChannelEvent": ("on_channel",),
}

FACING_DIRECTIONS = ["FrontRight", "FrontLeft", "BackRight", "BackLeft"]

HIGHRISE_WS_URI = "wss://highrise.game/web/botapi"
WEBAPI_BASE_URL = "https://webapi.highrise.game"
HIGHRISE_CLOUDFLARE_URL = "https://d4v5j9dz6t9fz.cloudfront.net/"

SERVER_ERRORS = [
    "Bots must have designer rights or be invited to enter a room.",
    "Invalid room id",
    "API token not found"
]

DEFAULT_OUTFIT = [
    OutfitItem(type='clothing', amount=1, id='body-flesh', account_bound=False, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='eye-f_09b', account_bound=False, active_palette=31), 
    OutfitItem(type='clothing', amount=1, id='eyebrow-n_08', account_bound=True, active_palette=79), 
    OutfitItem(type='clothing', amount=1, id='hair_front-n_basic2020overshoulderwavyshort', account_bound=True, active_palette=23), 
    OutfitItem(type='clothing', amount=1, id='hair_back-n_basic2020overshoulderwavyshort', account_bound=True, active_palette=23), 
    OutfitItem(type='clothing', amount=1, id='mouth-basic2018downturnedthinpeaked', account_bound=True, active_palette=1), 
    OutfitItem(type='clothing', amount=1, id='freckle-n_basic2018freckle22', account_bound=True, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='freckle-n_friendlymonstersmarchskypass2022friendlyblush', account_bound=True, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='freckle-n_basic2018freckle21', account_bound=True, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='dress-f_strapless_beige', account_bound=False, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='shoes-n_starteritems2019flatswhite', account_bound=True, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='pants-n_underwearstore2021blackspeedo', account_bound=True, active_palette=0), 
    OutfitItem(type='clothing', amount=1, id='nose-n_01', account_bound=True, active_palette=0)
]