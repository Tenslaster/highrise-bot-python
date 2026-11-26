"""Public Web API models for bots written against the Highrise SDK."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from highrise_fast._pycompat import StrEnum
from highrise_fast.models_webapi import (
    ItemCategory as ItemCategory,
)
from highrise_fast.models_webapi import (
    Rarity as Rarity,
)
from highrise_fast.models_webapi import (
    SearchItemsResponse as SearchItemsResponse,
)
from pendulum import DateTime


class LegacyRewardCategory(StrEnum):
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
    PROFILE_BACKGROUND = "profile_background"
    SET = "set"


class NFIStrategy(StrEnum):
    SEQUENTIAL = "sequential"
    TOTAL_DEFINED = "total_defined"
    POOL = "pool"


@dataclass(slots=True)
class OutfitItemColors:
    dependent_colors: Sequence[str] = ()
    palettes: Sequence[list] = ()
    linked_colors: str = ""


@dataclass(slots=True)
class OutfitItem:
    item_id: str
    name: str
    rarity: str
    active_palette: int
    parts: list[tuple[str, str]]
    colors: OutfitItemColors | None = None


@dataclass(slots=True)
class ActiveRoomInfo:
    id: str
    display_name: str
    code_name: str | None


@dataclass(slots=True)
class Crew:
    id: str
    name: str


@dataclass(slots=True)
class User:
    user_id: str
    username: str
    outfit: list[OutfitItem]
    bio: str
    joined_at: DateTime
    last_online_in: DateTime | None
    num_followers: int
    num_following: int
    num_friends: int
    active_room: ActiveRoomInfo | None
    country_code: str
    crew: Crew | None
    voice_enabled: bool
    discord_id: str | None = None


@dataclass(slots=True)
class UserBasic:
    user_id: str
    username: str | None = None
    created_at: str | None = None
    joined_at: str | None = None
    last_connect_at: str | None = None
    last_activity_at: str | None = None
    banned_until: str | None = None
    banned: bool = False


@dataclass(slots=True)
class Room:
    room_id: str
    disp_name: str
    created_at: str
    access_policy: str
    category: str
    owner_id: str
    locale: list[str] = field(default_factory=list)
    is_home_room: bool | None = None
    num_connected: int = 0
    moderator_ids: list[str] = field(default_factory=list)
    designer_ids: list[str] = field(default_factory=list)
    description: str | None = None
    crew_id: str | None = None
    bots: str | None = None
    indicators: str | None = None
    thumbnail_url: str | None = None
    banner_url: str | None = None


@dataclass(slots=True)
class RoomBasic:
    room_id: str
    disp_name: str
    description: str
    category: str
    owner_id: str
    created_at: str
    access_policy: str
    locale: list[str] = field(default_factory=list)
    is_home_room: bool | None = None
    designer_ids: list[str] = field(default_factory=list)
    moderator_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Comment:
    id: str
    content: str
    post_id: str
    author_id: str
    author_name: str
    num_likes: int


@dataclass(slots=True)
class PostItem:
    item_id: str
    active_palette: int = 0
    account_bound: bool = False


@dataclass(slots=True)
class PostInventory:
    items: list[PostItem]


@dataclass(slots=True)
class PostBody:
    text: str
    inventory: PostInventory


@dataclass(slots=True)
class PostBasic:
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


@dataclass(slots=True)
class Post(PostBasic):
    comments: list[Comment] = field(default_factory=list)


@dataclass(slots=True)
class SkinPart:
    bone: str
    slot: str
    image_file: str
    attachment_name: str | None = None
    has_remote_render_layer: bool | None = None


@dataclass(slots=True)
class ItemBasic:
    item_id: str
    item_name: str
    category: ItemCategory | None = None
    color_linked_categories: list[str] | None = field(default_factory=list)
    color_palettes: list[str] | None = field(default_factory=list)
    created_at: DateTime | None = None
    description_key: str | None = None
    gems_sale_price: int | None = None
    inspired_by: list[str] = field(default_factory=list)
    is_purchasable: bool = False
    is_tradable: bool = False
    image_url: str | None = None
    icon_url: str | None = None
    link_ids: list[str] = field(default_factory=list)
    m_dependent_colors: list[tuple[ItemCategory, int, int]] | None = field(default_factory=list)
    m_front_skin_part_list: list[SkinPart] = field(default_factory=list)
    m_back_skin_part_list: list[SkinPart] = field(default_factory=list)
    m_hidden_skin_parts: set[str] = field(default_factory=set)
    pops_sale_price: int | None = None
    rarity: Rarity = Rarity.NONE
    release_date: DateTime | None = None


@dataclass(slots=True)
class Item:
    item_id: str
    item_name: str
    acquisition_cost: int | None = None
    acquisition_amount: int | None = None
    acquisition_currency: str | None = None
    category: ItemCategory | None = None
    color_linked_categories: list[str] | None = field(default_factory=list)
    color_palettes: list[str] | None = field(default_factory=list)
    created_at: DateTime | None = None
    description_key: str | None = None
    gems_sale_price: int | None = None
    inspired_by: list[str] = field(default_factory=list)
    is_purchasable: bool = False
    is_tradable: bool = False
    image_url: str | None = None
    icon_url: str | None = None
    link_ids: list[str] = field(default_factory=list)
    m_dependent_colors: list[tuple[ItemCategory, int, int]] | None = field(default_factory=list)
    m_front_skin_part_list: list[SkinPart] = field(default_factory=list)
    m_back_skin_part_list: list[SkinPart] = field(default_factory=list)
    m_hidden_skin_parts: set[str] = field(default_factory=set)
    pops_sale_price: int | None = None
    rarity: Rarity = Rarity.NONE
    release_date: DateTime | None = None


@dataclass(slots=True)
class Affiliation:
    id: str
    title: str
    type: str
    event_type: str | None = None


@dataclass(slots=True)
class RelatedItem:
    item_id: str
    disp_name: str
    rarity: Rarity = Rarity.NONE


@dataclass(slots=True)
class RelatedItems:
    affiliations: list[Affiliation] = field(default_factory=list)
    items: list[RelatedItem] = field(default_factory=list)


@dataclass(slots=True)
class Seller:
    user_id: str
    username: str
    outfit: list[OutfitItem] = field(default_factory=list)
    last_connected_at: DateTime | None = None


@dataclass(slots=True)
class StorefrontListings:
    sellers: list[Seller] = field(default_factory=list)
    pages: int = 0
    total: int = 0


@dataclass(slots=True)
class NFIItemMetadata:
    item_number: int
    stack_id: str


@dataclass(slots=True)
class NFITemplateMetadata:
    strategy: NFIStrategy
    total_amount: int | None = None


@dataclass(slots=True)
class ItemMetadata:
    nfi_metadata: NFIItemMetadata | None = None
    nfi_template_metadata: NFITemplateMetadata | None = None


@dataclass(slots=True)
class Reward:
    category: LegacyRewardCategory
    amount: int
    reward_id: str = ""
    item_id: str | None = None
    account_bound: bool = False
    metadata: ItemMetadata | None = None


@dataclass(slots=True)
class LimitedKompuReward:
    expires_at: DateTime | None = None
    rewards: list[Reward] = field(default_factory=list)


@dataclass(slots=True)
class ProgressReward:
    rewards_at: int
    rewards: list[Reward] = field(default_factory=list)


@dataclass(slots=True)
class Grab:
    grab_id: str
    title: str
    description: str
    background_color: tuple[int, int, int]
    banner_img_url: str
    starts_at: DateTime | None = None
    expires_at: DateTime | None = None
    rewards: list[Reward] = field(default_factory=list)
    primary_img_url: str | None = None
    secondary_img_url: str | None = None
    costs: list[Reward] = field(default_factory=list)
    kompu_rewards: list[Reward] = field(default_factory=list)
    is_tradable: bool = True
    limited_time_kompu: LimitedKompuReward | None = None
    progress_reward: ProgressReward | None = None


@dataclass(slots=True)
class GetPublicUserResponse:
    user: User


@dataclass(slots=True)
class GetPublicUsersResponse:
    users: list[UserBasic]
    total: int
    first_id: str
    last_id: str


@dataclass(slots=True)
class GetPublicRoomResponse:
    room: Room


@dataclass(slots=True)
class GetPublicRoomsResponse:
    rooms: list[RoomBasic]
    total: int
    first_id: str
    last_id: str


@dataclass(slots=True)
class GetPublicPostResponse:
    post: Post


@dataclass(slots=True)
class GetPublicPostsResponse:
    posts: list[PostBasic]
    total: int
    first_id: str
    last_id: str


@dataclass(slots=True)
class GetPublicItemResponse:
    item: Item
    related_items: RelatedItems | None
    storefront_listings: StorefrontListings | None


@dataclass(slots=True)
class GetPublicItemsResponse:
    items: list[ItemBasic]
    total: int
    first_id: str
    last_id: str


@dataclass(slots=True)
class GetPublicGrabResponse:
    grab: Grab


@dataclass(slots=True)
class GetPublicGrabsResponse:
    grabs: list[Grab]
    total: int
    first_id: str
    last_id: str
