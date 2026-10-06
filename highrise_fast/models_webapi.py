"""Models, response wrappers, and routing helpers for the Highrise public WebAPI."""

from __future__ import annotations



from datetime import datetime

from enum import Enum, unique

from typing import Any



__all__ = [

    "AttrDict",

    "GetPublicGrabResponse",

    "GetPublicGrabsResponse",

    "GetPublicItemResponse",

    "GetPublicItemsResponse",

    "GetPublicPostResponse",

    "GetPublicPostsResponse",

    "GetPublicRoomResponse",

    "GetPublicRoomsResponse",

    "GetPublicUserResponse",

    "GetPublicUsersResponse",

    "ItemCategory",

    "Rarity",

    "parse_webapi_response",

]



@unique

class ItemCategory(str, Enum):

    """Enumeration of public WebAPI item categories."""

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

    """Enumeration of item rarity levels."""

    COMMON = "common"

    UNCOMMON = "uncommon"

    RARE = "rare"

    EPIC = "epic"

    LEGENDARY = "legendary"

    MYTHICAL = "mythical"

    NONE = "none"



_DATETIME_KEYS: frozenset[str] = frozenset(

    {

        "joined_at",

        "last_online_in",

        "created_at",

        "release_date",

        "starts_at",

        "expires_at",

        "last_connected_at",

    }

)



def _as_int(value: Any, default: int = 0) -> int:

    """Safely convert a value to int."""

    try:

        return int(value)

    except (TypeError, ValueError, OverflowError):

        return default



def _as_str(value: Any, default: str = "") -> str:

    """Safely convert a value to str."""

    if value is None:

        return default

    return str(value)



def _parse_datetime(value: str) -> datetime | str:

    """Parse an ISO-8601 datetime string when possible."""

    try:

        v = value.replace("Z", "+00:00")

        return datetime.fromisoformat(v)

    except (ValueError, TypeError):

        return value



def _wrap(value: Any) -> Any:

    """Recursively wrap dicts and lists for attribute-style access."""

    if isinstance(value, dict):

        return AttrDict(value)

    if isinstance(value, list):

        return [_wrap(v) for v in value]

    return value



def _wrap_keyed(value: Any, key: str) -> Any:

    """Wrap a value and parse known datetime fields."""

    if key in _DATETIME_KEYS and isinstance(value, str):

        return _parse_datetime(value)

    return _wrap(value)



class AttrDict:

    """Dictionary-like object that allows attribute access and caches parsed values."""

    __slots__ = ("_cache", "_raw")



    def __init__(self, raw: dict[str, Any]) -> None:

        """Initialize the instance."""

        object.__setattr__(self, "_raw", raw)

        object.__setattr__(self, "_cache", {})



    @property

    def raw(self) -> dict[str, Any]:

        """Return the underlying raw dictionary."""

        return object.__getattribute__(self, "_raw")



    def _resolve(self, key: str) -> Any:

        """Resolve and cache the value for a key."""

        cache = object.__getattribute__(self, "_cache")

        if key in cache:

            return cache[key]

        raw = object.__getattribute__(self, "_raw")

        if key not in raw:

            raise KeyError(key)

        value = raw[key]

        if key in _DATETIME_KEYS and isinstance(value, str):

            result = _parse_datetime(value)

        else:

            result = _wrap(value)

        cache[key] = result

        return result



    def __getattr__(self, name: str) -> Any:

        """Resolve attribute access."""

        try:

            return self._resolve(name)

        except KeyError:

            raise AttributeError(name) from None



    def __getitem__(self, key: str) -> Any:

        """Retrieve a value by key."""

        return self._resolve(key)



    def get(self, key: str, default: Any = None) -> Any:

        """Get a value with a default fallback."""

        try:

            return self._resolve(key)

        except KeyError:

            return default



    def keys(self):

        """Return dictionary keys."""

        return object.__getattribute__(self, "_raw").keys()



    def values(self):

        """Return dictionary values."""

        return object.__getattribute__(self, "_raw").values()



    def items(self):

        """Return dictionary items."""

        return object.__getattribute__(self, "_raw").items()



    def __contains__(self, key: str) -> bool:

        """Return True when the given key exists."""

        return key in object.__getattribute__(self, "_raw")



    def __iter__(self):

        """Return an iterator over the object."""

        return iter(object.__getattribute__(self, "_raw"))



    def __len__(self) -> int:

        """Return the number of stored entries."""

        return len(object.__getattribute__(self, "_raw"))



    def __repr__(self) -> str:

        """Return a developer-friendly representation."""

        return f"AttrDict({object.__getattribute__(self, '_raw')!r})"



class _Base:

    """Base class for public WebAPI response objects."""

    __slots__ = ("_cache", "_raw")



    def __init__(self, raw: Any) -> None:

        """Initialize the instance."""

        object.__setattr__(self, "_raw", raw if isinstance(raw, dict) else {})

        object.__setattr__(self, "_cache", {})



    @property

    def raw(self) -> dict[str, Any]:

        """Return the underlying raw dictionary."""

        return object.__getattribute__(self, "_raw")



    def _get(self, key: str, default: Any = None) -> Any:

        """Get a value with cache management and conditional parsing."""

        cache = object.__getattribute__(self, "_cache")

        if key in cache:

            return cache[key]

        raw = object.__getattribute__(self, "_raw")

        if key in raw:

            val = _wrap_keyed(raw[key], key)

            cache[key] = val

            return val

        return default



    def __getattr__(self, name: str) -> Any:

        """Resolve attribute access."""

        cache = object.__getattribute__(self, "_cache")

        if name in cache:

            return cache[name]

        raw = object.__getattribute__(self, "_raw")

        if name in raw:

            val = _wrap_keyed(raw[name], name)

            cache[name] = val

            return val

        raise AttributeError(name)



    def __repr__(self) -> str:

        """Return a developer-friendly representation."""

        return f"{type(self).__name__}({object.__getattribute__(self, '_raw')!r})"





class GetPublicUserResponse(_Base):

    """Response payload for a single public user."""

    @property

    def user(self) -> Any:

        """Return User."""

        return self._get("user")



class GetPublicUsersResponse(_Base):

    """Paginated response payload for public users."""

    @property

    def users(self) -> Any:

        """Return Users."""

        return self._get("users", [])



    @property

    def total(self) -> int:

        """Return Total."""

        return _as_int(self._raw.get("total"), 0)



    @property

    def first_id(self) -> str:

        """Return First id."""

        return _as_str(self._raw.get("first_id"))



    @property

    def last_id(self) -> str:

        """Return Last id."""

        return _as_str(self._raw.get("last_id"))



class GetPublicRoomResponse(_Base):

    """Response payload for a single public room."""

    @property

    def room(self) -> Any:

        """Return Room."""

        return self._get("room")



class GetPublicRoomsResponse(_Base):

    """Paginated response payload for public rooms."""

    @property

    def rooms(self) -> Any:

        """Return Rooms."""

        return self._get("rooms", [])



    @property

    def total(self) -> int:

        """Return Total."""

        return _as_int(self._raw.get("total"), 0)



    @property

    def first_id(self) -> str:

        """Return First id."""

        return _as_str(self._raw.get("first_id"))



    @property

    def last_id(self) -> str:

        """Return Last id."""

        return _as_str(self._raw.get("last_id"))



class GetPublicPostResponse(_Base):

    """Response payload for a single public post."""

    @property

    def post(self) -> Any:

        """Return Post."""

        return self._get("post")



class GetPublicPostsResponse(_Base):

    """Paginated response payload for public posts."""

    @property

    def posts(self) -> Any:

        """Return Posts."""

        return self._get("posts", [])



    @property

    def total(self) -> int:

        """Return Total."""

        return _as_int(self._raw.get("total"), 0)



    @property

    def first_id(self) -> str:

        """Return First id."""

        return _as_str(self._raw.get("first_id"))



    @property

    def last_id(self) -> str:

        """Return Last id."""

        return _as_str(self._raw.get("last_id"))



class GetPublicItemResponse(_Base):

    """Response payload for a single public item."""

    @property

    def item(self) -> Any:

        """Return Item."""

        return self._get("item")



    @property

    def related_items(self) -> Any:

        """Return Related items."""

        return self._get("related_items")



    @property

    def storefront_listings(self) -> Any:

        """Return Storefront listings."""

        return self._get("storefront_listings")



class GetPublicItemsResponse(_Base):

    """Paginated response payload for public items."""

    @property

    def items(self) -> Any:

        """Return Items."""

        return self._get("items", [])



    @property

    def total(self) -> int:

        """Return Total."""

        return _as_int(self._raw.get("total"), 0)



    @property

    def first_id(self) -> str:

        """Return First id."""

        return _as_str(self._raw.get("first_id"))



    @property

    def last_id(self) -> str:

        """Return Last id."""

        return _as_str(self._raw.get("last_id"))



class GetPublicGrabResponse(_Base):

    """Response payload for a single public grab."""

    @property

    def grab(self) -> Any:

        """Return Grab."""

        return self._get("grab")



class GetPublicGrabsResponse(_Base):

    """Paginated response payload for public grabs."""

    @property

    def grabs(self) -> Any:

        """Return Grabs."""

        return self._get("grabs", [])



    @property

    def total(self) -> int:

        """Return Total."""

        return _as_int(self._raw.get("total"), 0)



    @property

    def first_id(self) -> str:

        """Return First id."""

        return _as_str(self._raw.get("first_id"))



    @property

    def last_id(self) -> str:

        """Return Last id."""

        return _as_str(self._raw.get("last_id"))





def _segments(endpoint: str) -> list[str]:

    """Extract path segments from an endpoint URL."""

    path = endpoint.split("?", 1)[0]

    return [part for part in path.strip("/").split("/") if part]



def parse_webapi_response(endpoint: str, data: Any) -> Any:

    """Route a public WebAPI JSON payload to the matching response class."""

    if not isinstance(data, dict):

        return data

    parts = _segments(endpoint)

    if not parts:

        return data

    root = parts[0]

    if root == "users":

        return (

            GetPublicUserResponse(data)

            if len(parts) > 1

            else GetPublicUsersResponse(data)

        )

    if root == "rooms":

        return (

            GetPublicRoomResponse(data)

            if len(parts) > 1

            else GetPublicRoomsResponse(data)

        )

    if root == "posts":

        return (

            GetPublicPostResponse(data)

            if len(parts) > 1

            else GetPublicPostsResponse(data)

        )

    if root == "items":

        return (

            GetPublicItemResponse(data)

            if len(parts) > 1

            else GetPublicItemsResponse(data)

        )

    if root == "grabs":

        return (

            GetPublicGrabResponse(data)

            if len(parts) > 1

            else GetPublicGrabsResponse(data)

        )

    return data