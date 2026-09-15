from dataclasses import dataclass
from typing import Callable, Coroutine, Any
from datetime import datetime
from .webapi_models import *
from ..base_response import BaseResponse
from ..websocket.responses import ResponseIterator
from ...constants import HIGHRISE_CLOUDFLARE_URL

def _parse_web_outfit_item(raw: dict) -> WebOutfitItem:
    """Shared parser for outfit items as returned by the web API
    (used by both GetPublicUserResponse and GetPublicItemResponse)."""
    raw_colors = raw.get("colors")
    colors = WebOutfitItemColors(**raw_colors) if raw_colors else None

    return WebOutfitItem(
        item_id=raw.get("item_id", ""),
        name=raw.get("name", ""),
        rarity=raw.get("rarity", ""),
        active_palette=raw.get("active_palette", 0),
        parts=[tuple(p) for p in raw.get("parts", [])],
        colors=colors,
    )

@dataclass
class GetPublicUserResponse(BaseResponse):
    """Response for `GET /users/{user_id/username}`."""
    user: PublicUser | None = None

    def _build(self, data: dict) -> None:
        raw_user = data.get("user", {})
        self.user = self._parse_user(raw_user)

    @staticmethod
    def _parse_user(raw: dict) -> PublicUser:
        raw_active_room = raw.get("active_room")
        active_room = ActiveRoomInfo(**raw_active_room) if raw_active_room else None

        raw_crew = raw.get("crew")
        crew = Crew(**raw_crew) if raw_crew else None

        raw_outfit = raw.get("outfit", [])
        outfit = [_parse_web_outfit_item(item) for item in raw_outfit]

        last_online_in = raw.get("last_online_in")

        return PublicUser(
            user_id=raw.get("user_id", ""),
            username=raw.get("username", ""),
            outfit=outfit,
            bio=raw.get("bio", ""),
            joined_at=datetime.fromisoformat(raw["joined_at"]),
            last_online_in=datetime.fromisoformat(last_online_in) if last_online_in else None,
            num_followers=raw.get("num_followers", 0),
            num_following=raw.get("num_following", 0),
            num_friends=raw.get("num_friends", 0),
            active_room=active_room,
            country_code=raw.get("country_code", ""),
            crew=crew,
            voice_enabled=raw.get("voice_enabled", False),
            discord_id=raw.get("discord_id"),
            icon_url=raw.get("icon_url"),
            avatar_url=raw.get("avatar_url"),
            avatar_svg=raw.get("avatar_svg"),
        )

@dataclass
class GetPublicRoomResponse(BaseResponse):
    """ Response for `GET /rooms/{room_id}`"""
    room: PublicRoom | None = None

    def _build(self, data: dict):
        raw_room = data.get('room', {})

        self.room = PublicRoom(
            room_id=raw_room.get('room_id', ''),
            access_policy=raw_room.get('access_policy', ''),
            banner_url=raw_room.get('banner_url', ''),
            bots=raw_room.get('bots', ''),
            category=raw_room.get('category', ''),
            created_at=datetime.fromisoformat(raw_room.get('created_at', '')),
            crew_id=raw_room.get('crew_id', ''),
            description=raw_room.get('description', ''),
            designer_ids=raw_room.get('designer_ids') or [],
            moderator_ids=raw_room.get('moderator_ids') or [],
            disp_name=raw_room.get('disp_name', ''),
            indicators=raw_room.get('indicators'),
            is_home_room=raw_room.get('is_home_room', False),
            locale=raw_room.get('locale') or [],
            num_connected=raw_room.get('num_connected', 0),
            owner_id=raw_room.get('owner_id', ''),
            thumbnail_url=raw_room.get('thumbnail_url', '')
        )

@dataclass
class GetPublicRoomsResponse(BaseResponse):
    """Response for `GET /rooms?` (list endpoint)"""
    rooms: list[PublicRoomBasic] = field(default_factory=list)
    total: int = 0
    first_id: str = ""
    last_id: str = ""
    next_page_fn: Callable[[], Coroutine[Any, Any, "GetPublicRoomsResponse"]] | None = None

    def _build(self, data: dict) -> None:
        raw_rooms = data.get("rooms", [])
        
        self.rooms = [self._parse_room(r) for r in raw_rooms]
        self.total = data.get("total", 0)
        self.first_id = data.get("first_id", "")
        self.last_id = data.get("last_id", "")

    @staticmethod
    def _parse_room(raw: dict) -> PublicRoomBasic:
        created_at_raw = raw.get("created_at")
        created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else None

        return PublicRoomBasic(
            room_id=raw.get("room_id", ""),
            disp_name=raw.get("disp_name", ""),
            description=raw.get("description", ""),
            category=raw.get("category", ""),
            owner_id=raw.get("owner_id", ""),
            created_at=created_at,
            access_policy=raw.get("access_policy", ""),
            locale=raw.get("locale") or [],
            is_home_room=raw.get("is_home_room"),
            designer_ids=raw.get("designer_ids") or [],
            moderator_ids=raw.get("moderator_ids") or [],
        )

    def __aiter__(self) -> "ResponseIterator[GetPublicRoomsResponse]":
        return ResponseIterator(self)
    
@dataclass
class GetPublicPostResponse(BaseResponse):
    """Response for `GET /posts/{post_id}`"""
    post: PublicPost | None = None

    def _build(self, data: dict):
        raw_post = data.get('post', {})
        raw_comments = raw_post.get("comments", [])

        self.post = PublicPost(
            post_id=raw_post.get("post_id"),
            author_id=raw_post.get("author_id"),
            created_at=raw_post.get("created_at"),
            file_key=f"{HIGHRISE_CLOUDFLARE_URL}{raw_post.get('file_key')}" if raw_post.get('file_key') else None,            type=raw_post.get("type"),
            visibility=raw_post.get("visibility", "private"),
            num_comments=raw_post.get("num_comments", 0),
            num_likes=raw_post.get("num_likes", 0),
            num_reposts=raw_post.get("num_reposts", 0),
            body= self._parse_post_body(raw_post.get("body", {})),
            caption=raw_post.get("caption"),
            featured_user_ids=raw_post.get("featured_user_ids", []),
            comments=[Comment(**comment) for comment in raw_comments]
        )

    @staticmethod
    def _parse_post_body(body: dict) -> PostBody:
        inventory_dict = body.get('inventory', {})
        inventory_items = inventory_dict.get('items') or []

        post_inventory = PostInventory(
            items=[PostItem(**item) for item in inventory_items]
        )

        return PostBody(
            text=body.get('text', ''),
            inventory=post_inventory
        )

@dataclass
class GetPublicPostsResponse(BaseResponse):
    """Response for `GET /posts?` (list endpoint)"""
    posts: list[PublicPostBasic] = field(default_factory=list)
    total: int = 0
    first_id: str = ""
    last_id: str = ""
    next_page_fn: Callable[[], Coroutine[Any, Any, "GetPublicPostsResponse"]] | None = None

    def _build(self, data: dict) -> None:
        raw_posts = data.get("posts", [])
        self.posts = [self._parse_post(p) for p in raw_posts]
        self.total = data.get("total", 0)
        self.first_id = data.get("first_id", "")
        self.last_id = data.get("last_id", "")

    @staticmethod
    def _parse_post(raw_post: dict) -> PublicPostBasic:
        raw_body = raw_post.get("body")
        body = PostBody(**raw_body) if raw_body else None
        file_key = raw_post.get("file_key")

        return PublicPostBasic(
            post_id=raw_post.get("post_id"),
            author_id=raw_post.get("author_id"),
            created_at=raw_post.get("created_at"),
            file_key=f"{HIGHRISE_CLOUDFLARE_URL}{file_key}" if file_key else None,
            type=raw_post.get("type"),
            visibility=raw_post.get("visibility", "private"),
            num_comments=raw_post.get("num_comments", 0),
            num_likes=raw_post.get("num_likes", 0),
            num_reposts=raw_post.get("num_reposts", 0),
            body=body,
            caption=raw_post.get("caption"),
            featured_user_ids=raw_post.get("featured_user_ids") or [],
        )

    def __aiter__(self) -> "ResponseIterator[GetPublicPostsResponse]":
        return ResponseIterator(self)

@dataclass
class SearchItemsResponse(BaseResponse):
    """Response for GET `/items/search?` (list endpoint)."""
    items: list[ItemBasic] = field(default_factory=list)
    next_page_fn: Callable[[], Coroutine[Any, Any, "SearchItemsResponse"]] | None = None

    def _build(self, data: dict) -> None:
        raw_items = data.get("items", [])
        self.items = [self._parse_item(i) for i in raw_items]

    @staticmethod
    def _parse_item(raw: dict) -> ItemBasic:
        created_at_raw = raw.get("created_at")
        release_date_raw = raw.get("release_date")

        raw_category = raw.get("category")
        raw_rarity = raw.get("rarity")

        front_parts = [SearchItemsResponse._parse_skin_part(p) for p in raw.get("m_front_skin_part_list") or []]
        back_parts = [SearchItemsResponse._parse_skin_part(p) for p in raw.get("m_back_skin_part_list") or []]

        return ItemBasic(
            item_id=raw.get("item_id", ""),
            item_name=raw.get("item_name", ""),
            category=ItemCategory(raw_category) if raw_category else None,
            color_linked_categories=raw.get("color_linked_categories") or [],
            color_palettes=raw.get("color_palettes") or [],
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else None,
            description_key=raw.get("description_key"),
            gems_sale_price=raw.get("gems_sale_price"),
            inspired_by=raw.get("inspired_by") or [],
            is_purchasable=raw.get("is_purchasable", False),
            is_tradable=raw.get("is_tradable", False),
            image_url=raw.get("image_url"),
            icon_url=raw.get("icon_url"),
            link_ids=raw.get("link_ids") or [],
            m_dependent_colors=[tuple(x) for x in raw.get("m_dependent_colors") or []],
            m_front_skin_part_list=front_parts,
            m_back_skin_part_list=back_parts,
            m_hidden_skin_parts=set(raw.get("m_hidden_skin_parts") or []),
            pops_sale_price=raw.get("pops_sale_price"),
            rarity=Rarity(raw_rarity) if raw_rarity else Rarity.NONE,
            release_date=datetime.fromisoformat(release_date_raw) if release_date_raw else None,
        )

    @staticmethod
    def _parse_skin_part(raw: dict) -> SkinPart:
        return SkinPart(
            bone=raw.get("bone", ""),
            slot=raw.get("slot", ""),
            image_file=raw.get("imageFile", ""),
            attachment_name=raw.get("attachmentName"),
            has_remote_render_layer=raw.get("hasRemoteRenderLayer"),
        )

    def __aiter__(self) -> "ResponseIterator[SearchItemsResponse]":
        return ResponseIterator(self)

@dataclass
class GetPublicItemResponse(BaseResponse):
    """Response for GET `/items/{item_id}`."""
    item: Item | None = None
    related_items: RelatedItems | None = None
    storefront_listings: StorefrontListings | None = None

    def _build(self, data: dict) -> None:
        raw_item = data.get("item")
        self.item = self._parse_item(raw_item) if raw_item else None

        raw_related = data.get("related_items")
        self.related_items = self._parse_related_items(raw_related) if raw_related else None

        raw_storefront = data.get("storefront_listings")
        self.storefront_listings = self._parse_storefront(raw_storefront) if raw_storefront else None

    @staticmethod
    def _parse_item(raw: dict) -> Item:
        created_at_raw = raw.get("created_at")
        release_date_raw = raw.get("release_date")

        raw_category = raw.get("category")
        raw_rarity = raw.get("rarity")

        front_parts = [SearchItemsResponse._parse_skin_part(p) for p in raw.get("m_front_skin_part_list") or []]
        back_parts = [SearchItemsResponse._parse_skin_part(p) for p in raw.get("m_back_skin_part_list") or []]

        return Item(
            item_id=raw.get("item_id", ""),
            item_name=raw.get("item_name", ""),
            category=ItemCategory(raw_category) if raw_category else None,
            color_linked_categories=raw.get("color_linked_categories") or [],
            color_palettes=raw.get("color_palettes") or [],
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else None,
            description_key=raw.get("description_key"),
            gems_sale_price=raw.get("gems_sale_price"),
            inspired_by=raw.get("inspired_by") or [],
            is_purchasable=raw.get("is_purchasable", False),
            is_tradable=raw.get("is_tradable", False),
            image_url=raw.get("image_url"),
            icon_url=raw.get("icon_url"),
            link_ids=raw.get("link_ids") or [],
            m_dependent_colors=[tuple(x) for x in raw.get("m_dependent_colors") or []],
            m_front_skin_part_list=front_parts,
            m_back_skin_part_list=back_parts,
            m_hidden_skin_parts=set(raw.get("m_hidden_skin_parts") or []),
            pops_sale_price=raw.get("pops_sale_price"),
            rarity=Rarity(raw_rarity) if raw_rarity else Rarity.NONE,
            release_date=datetime.fromisoformat(release_date_raw) if release_date_raw else None,
            acquisition_cost=raw.get("acquisition_cost"),
            acquisition_amount=raw.get("acquisition_amount"),
            acquisition_currency=raw.get("acquisition_currency"),
        )

    @staticmethod
    def _parse_related_items(raw: dict) -> RelatedItems:
        affiliations = [Affiliation(**a) for a in raw.get("affiliations") or []]
        items = [RelatedItem(item_id=i.get("item_id", ""), disp_name=i.get("disp_name", ""),
                              rarity=Rarity(i["rarity"]) if i.get("rarity") else Rarity.NONE)
                 for i in raw.get("items") or []]
        return RelatedItems(affiliations=affiliations, items=items)

    @staticmethod
    def _parse_storefront(raw: dict) -> StorefrontListings:
        sellers = [
            Seller(
                user_id=s.get("user_id", ""),
                username=s.get("username", ""),
                outfit=[_parse_web_outfit_item(i) for i in s.get('outfit')],  
                last_connected_at=datetime.fromisoformat(s["last_connected_at"]) if s.get("last_connected_at") else None,
            )
            for s in raw.get("sellers") or []
        ]
        return StorefrontListings(
            sellers=sellers,
            pages=raw.get("pages", 0),
            total=raw.get("total", 0),
        )

@dataclass
class GetPublicItemsResponse(BaseResponse):
    """Response for `GET /items? (list endpoint)`."""
    items: list[ItemBasic] = field(default_factory=list)
    total: int = 0
    first_id: str = ""
    last_id: str = ""
    next_page_fn: Callable[[], Coroutine[Any, Any, "GetPublicItemsResponse"]] | None = None

    def _build(self, data: dict) -> None:
        raw_items = data.get("items", [])
        self.items = [SearchItemsResponse._parse_item(i) for i in raw_items]
        self.total = data.get("total", 0)
        self.first_id = data.get("first_id", "")
        self.last_id = data.get("last_id", "")

    def __aiter__(self) -> "ResponseIterator[GetPublicItemsResponse]":
        return ResponseIterator(self)

@dataclass
class GetPublicGrabResponse(BaseResponse):
    """Response for GET `/grabs/{grab_id}`."""
    grab: Grab | None = None

    def _build(self, data: dict) -> None:
        raw_grab = data.get("grab")
        self.grab = self._parse_grab(raw_grab) if raw_grab else None

    @staticmethod
    def _parse_reward(raw: dict) -> Reward:
        raw_metadata = raw.get("metadata")
        metadata = GetPublicGrabResponse._parse_metadata(raw_metadata) if raw_metadata else None

        return Reward(
            category=LegacyRewardCategory(raw.get("category")),
            amount=raw.get("amount", 0),
            reward_id=raw.get("reward_id", ""),
            item_id=raw.get("item_id"),
            account_bound=raw.get("account_bound", False),
            metadata=metadata,
        )

    @staticmethod
    def _parse_metadata(raw: dict) -> ItemMetadata:
        raw_nfi = raw.get("nfi_metadata")
        nfi_metadata = NFIItemMetadata(**raw_nfi) if raw_nfi else None

        raw_template = raw.get("nfi_template_metadata")
        nfi_template_metadata = None
        if raw_template:
            nfi_template_metadata = NFITemplateMetadata(
                strategy=NFIStrategy(raw_template.get("strategy")),
                total_amount=raw_template.get("total_amount"),
            )

        return ItemMetadata(
            nfi_metadata=nfi_metadata,
            nfi_template_metadata=nfi_template_metadata,
        )

    @staticmethod
    def _parse_grab(raw: dict) -> Grab:
        starts_at_raw = raw.get("starts_at")
        expires_at_raw = raw.get("expires_at")

        raw_limited_kompu = raw.get("limited_time_kompu")
        limited_time_kompu = None
        if raw_limited_kompu:
            kompu_expires_raw = raw_limited_kompu.get("expires_at")
            limited_time_kompu = LimitedKompuReward(
                expires_at=datetime.fromisoformat(kompu_expires_raw) if kompu_expires_raw else None,
                rewards=[GetPublicGrabResponse._parse_reward(r) for r in raw_limited_kompu.get("rewards") or []],
            )

        raw_progress = raw.get("progress_reward")
        progress_reward = None
        if raw_progress:
            progress_reward = ProgressReward(
                rewards_at=raw_progress.get("rewards_at", 0),
                rewards=[GetPublicGrabResponse._parse_reward(r) for r in raw_progress.get("rewards") or []],
            )

        return Grab(
            grab_id=raw.get("grab_id", ""),
            title=raw.get("title", ""),
            description=raw.get("description", ""),
            background_color=tuple(raw.get("background_color", (0, 0, 0))),
            banner_img_url=raw.get("banner_img_url", ""),
            starts_at=datetime.fromisoformat(starts_at_raw) if starts_at_raw else None,
            expires_at=datetime.fromisoformat(expires_at_raw) if expires_at_raw else None,
            rewards=[GetPublicGrabResponse._parse_reward(r) for r in raw.get("rewards") or []],
            primary_img_url=raw.get("primary_img_url"),
            secondary_img_url=raw.get("secondary_img_url"),
            costs=[GetPublicGrabResponse._parse_reward(r) for r in raw.get("costs") or []],
            kompu_rewards=[GetPublicGrabResponse._parse_reward(r) for r in raw.get("kompu_rewards") or []],
            is_tradable=raw.get("is_tradable", True),
            limited_time_kompu=limited_time_kompu,
            progress_reward=progress_reward,
        )

@dataclass
class GetPublicGrabsResponse(BaseResponse):
    """Response for `GET /grabs` (list endpoint)."""
    grabs: list[Grab] = field(default_factory=list)
    total: int = 0
    first_id: str = ""
    last_id: str = ""
    next_page_fn: Callable[[], Coroutine[Any, Any, "GetPublicGrabsResponse"]] | None = None

    def _build(self, data: dict) -> None:
        raw_grabs = data.get("grabs", [])
        self.grabs = [GetPublicGrabResponse._parse_grab(g) for g in raw_grabs]
        self.total = data.get("total", 0)
        self.first_id = data.get("first_id", "")
        self.last_id = data.get("last_id", "")

    def __aiter__(self) -> "ResponseIterator[GetPublicGrabsResponse]":
        return ResponseIterator(self)