from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from collections.abc import Sequence
from enum import Enum, unique

SortOptions = Literal["desc", "asc"]

@unique
class ItemCategory(str, Enum):
    """Every equippable item category on Highrise."""
    BAG = "bag"
    BLUSH = "blush"
    BODY = "body"
    DRESS = "dress"
    EARRINGS = "earrings"
    EMOTE = "emote"
    EYE = "eye"
    EYEBROW = "eyebrow"
    FACE_HAIR = "face_hair"
    FISHING_ROD = "fishing_rod"
    FRECKLE = "freckle"
    GLASSES = "glasses"
    GLOVES = "gloves"
    HAIR_BACK = "hair_back"
    HAIR_FRONT = "hair_front"
    HANDBAG = "handbag"
    HAT = "hat"
    JACKET = "jacket"
    LASHES = "lashes"
    MOLE = "mole"
    MOUTH = "mouth"
    NECKLACE = "necklace"
    NOSE = "nose"
    PANTS = "pants"
    SHIRT = "shirt"
    SHOES = "shoes"
    SHORTS = "shorts"
    SKIRT = "skirt"
    WATCH = "watch"
    FULLSUIT = "fullsuit"
    SOCK = "sock"
    TATTOO = "tattoo"
    ROD = "rod"
    AURA = "aura"
    
@unique
class Rarity(str, Enum):
    """Item rarity tiers, from most to least common."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHICAL = 'mythical'
    NONE = "none_"
    
@unique
class LegacyRewardCategory(str, Enum):
    """Currency/reward types a Reward can grant."""
    POPS = "pops"
    GEMS = "gems"
    OUTFIT = "outfit"
    GACHA_TOKENS = "gacha_tokens"
    FURNITURE = "furniture"
    COLLECTIBLE = "collectible"
    LUCKY_TOKENS = "lucky_tokens"
    EVENT_TICKETS = "event_tickets"
    EMOTE = "emote"
    GIFT_BOX = "gift_box"
    ENERGY = "energy"
    VIP_DAYS = "vip_days"
    CHIPS = "chips"
    PROMO_TOKENS = "promo_tokens"
    SKYPASS_STARS = "skypass_stars"
    ROOM_BOOST_TOKENS = "room_boost_tokens"
    ROOM_VOICE_TOKENS = "room_voice_tokens"
    POCKET_COINS = "pocket_coins"
    CASH = "cash"
    CUSTOM_CURRENCY = "custom_currency"
    PET = "pet"
    
@unique
class NFIStrategy(str, Enum):
    """How a non-fungible item's numbered instances are allocated."""
    SEQUENTIAL = "sequential"
    TOTAL_DEFINED = "total_defined"
    POOL = "pool"
    
@dataclass
class WebOutfitItemColors:
    """Color/palette data for a single web-API outfit item."""
    dependent_colors: Sequence[str] = field(default_factory=tuple)
    palettes: Sequence[list] = field(default_factory=tuple)
    linked_colors: str = ""
    
@dataclass
class WebOutfitItem:
    """A single outfit item as returned by the public web API.
    Distinct shape from the WebSocket API's OutfitItem."""
    item_id: str
    name: str
    rarity: Rarity
    active_palette: int
    parts: list[tuple[str, str]]
    colors: WebOutfitItemColors | None = None
    
@dataclass
class ActiveRoomInfo:
    """The room a user is currently active in, if any."""
    id: str
    display_name: str
    code_name: str | None
    
@dataclass
class Crew:
    """A user's crew."""
    id: str
    name: str
    
@dataclass
class PublicUser:
    """A user's public profile, as returned by `GET /users/{user_id}`."""
    user_id: str
    username: str
    bio: str
    joined_at: datetime
    last_online_in: datetime | None
    num_followers: int
    num_following: int
    num_friends: int
    active_room: ActiveRoomInfo | None
    country_code: str
    crew: Crew | None
    voice_enabled: bool
    discord_id: str | None = None
    icon_url: str | None = None
    avatar_url: str | None = None
    avatar_svg: str | None = None
    outfit: list[WebOutfitItem] = field(default_factory=list)
    
@dataclass
class PublicRoomBasic:
    """A lighter room shape, as returned by `GET /rooms` (list endpoint)."""
    room_id: str
    disp_name: str
    created_at: datetime | None
    access_policy: str
    category: str
    owner_id: str
    description: str
    is_home_room: bool | None = None
    locale: list[str] = field(default_factory=list)
    designer_ids: list[str] = field(default_factory=list)
    moderator_ids: list[str] = field(default_factory=list)
    
@dataclass
class PublicRoom(PublicRoomBasic):
    """A room's public data, as returned by `GET /rooms/{room_id}`.
    Extends PublicRoomBasic with fields only present on the single-room endpoint."""
    num_connected: int = 0  
    crew_id: str | None = None
    bots: str | None = None
    indicators: str | None = None
    thumbnail_url: str | None = None
    banner_url: str | None = None
    
@dataclass
class PostItem:
    """Single post item"""
    item_id: str
    active_palette: int = 0
    account_bound: bool = False
    
@dataclass
class PostInventory:
    """The set of items attached to a post."""
    items: list[PostItem] = field(default_factory=list)
    
@dataclass
class PostBody:
    """A post's text content plus any attached inventory items."""
    text: str
    inventory: PostInventory
    
@dataclass
class Comment:
    """Single post comment"""
    id: str
    content: str
    post_id: str
    author_id: str
    author_name: str
    num_likes: int
    
@dataclass
class PublicPostBasic:
    """A lighter post shape, as returned by `GET /post` (list endpoint)"""
    post_id: str
    author_id: str | None = None
    created_at: str | None = None
    file_key: str | None = None  
    type: str | None = None
    visibility: str = "private"
    num_comments: int = 0
    num_likes: int = 0
    num_reposts: int = 0
    body: PostBody | None = None
    caption: str | None = None
    featured_user_ids: list[str] = field(default_factory=list)
    
@dataclass
class PublicPost(PublicPostBasic):
    """A post's public data, as returned by `GET /post/{post_id}`.
    Extends PublicPostBasic with comments, only present on the single-post endpoint."""
    comments: list[Comment] = field(default_factory=list)
    
@dataclass
class SkinPart:
    """A single skin part attachment on an item."""
    bone: str
    slot: str
    image_file: str
    attachment_name: str | None = None
    has_remote_render_layer: bool | None = None
    
@dataclass
class ItemBasic:
    """A single item, as returned by `GET /items/search`."""
    item_id: str
    item_name: str
    category: ItemCategory | None = None
    color_linked_categories: list[str] = field(default_factory=list)
    color_palettes: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    description_key: str | None = None
    gems_sale_price: int | None = None
    inspired_by: list[str] = field(default_factory=list)
    is_purchasable: bool = False
    is_tradable: bool = False
    image_url: str | None = None
    icon_url: str | None = None
    link_ids: list[str] = field(default_factory=list)
    m_dependent_colors: list[tuple[ItemCategory, int, int]] = field(default_factory=list)
    m_front_skin_part_list: list[SkinPart] = field(default_factory=list)
    m_back_skin_part_list: list[SkinPart] = field(default_factory=list)
    m_hidden_skin_parts: set = field(default_factory=set)
    pops_sale_price: int | None = None
    rarity: Rarity = Rarity.NONE
    release_date: datetime | None = None
    
@dataclass
class Item(ItemBasic):
    """A full item, as returned by `GET /items/{item_id}`."""
    acquisition_cost: int | None = None
    acquisition_amount: int | None = None
    acquisition_currency: str | None = None
    
@dataclass
class Affiliation:
    """A collection/event an item or grab is associated with."""
    id: str
    title: str
    type: str
    event_type: str | None = None
    
@dataclass
class RelatedItem:
    """A lightweight reference to another item, used in RelatedItems."""
    item_id: str
    disp_name: str
    rarity: Rarity = Rarity.NONE
    
@dataclass
class RelatedItems:
    """Items and affiliations related to a given item, returned alongside `GetPublicItemResponse`."""
    affiliations: list[Affiliation] = field(default_factory=list)
    items: list[RelatedItem] = field(default_factory=list)
    
@dataclass
class Seller:
    """A user currently selling an item on the storefront."""
    user_id: str
    username: str
    outfit: list[WebOutfitItem] = field(default_factory=list)
    last_connected_at: datetime | None = None
    
@dataclass
class StorefrontListings:
    """Active sellers for an item, returned alongside `GetPublicItemResponse`."""
    sellers: list[Seller] = field(default_factory=list)
    pages: int = 0
    total: int = 0
    
@dataclass
class NFIItemMetadata:
    """Identifies a specific numbered instance of a non-fungible item."""
    item_number: int
    stack_id: str
    

@dataclass
class NFITemplateMetadata:
    """Allocation rules for a non-fungible item template."""
    strategy: NFIStrategy
    total_amount: int | None = None
    

@dataclass
class ItemMetadata:
    """Non-fungible item metadata attached to a Reward, if applicable."""
    nfi_metadata: NFIItemMetadata | None = None
    nfi_template_metadata: NFITemplateMetadata | None = None
    

@dataclass
class Reward:
    """A single reward or cost entry within a Grab."""
    category: LegacyRewardCategory
    amount: int
    reward_id: str = ""
    item_id: str | None = None
    account_bound: bool = False
    metadata: ItemMetadata | None = None
    

@dataclass
class LimitedKompuReward:
    """A time-limited bonus rewards granted once all costs in a Grab are collected."""
    expires_at: datetime | None = None
    rewards: list[Reward] = field(default_factory=list)
    

@dataclass
class ProgressReward:
    """A bonus reward granted after reaching a specific progress threshold in a Grab."""
    rewards_at: int  
    rewards: list[Reward] = field(default_factory=list)
    
@dataclass
class Grab:
    """A Grab event, as returned by `GET /grabs/{grab_id}`."""
    grab_id: str
    title: str
    description: str
    background_color: tuple[int, int, int]  
    banner_img_url: str
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    rewards: list[Reward] = field(default_factory=list)
    primary_img_url: str | None = None
    secondary_img_url: str | None = None
    costs: list[Reward] = field(default_factory=list)  
    kompu_rewards: list[Reward] = field(default_factory=list)  
    is_tradable: bool = True
    limited_time_kompu: LimitedKompuReward | None = None
    progress_reward: ProgressReward | None = None