"""
highrise_fast.models_webapi — typed-ish WebAPI response wrappers.

This module intentionally avoids attrs/cattrs. It provides lightweight
attribute-access wrappers over the raw JSON responses so code like this works:

    resp = await webapi.get_user(user_id)
    print(resp.user.username)

Date parsing is surgical: only known datetime fields are converted.
This avoids mangling user text that happens to look like a date
(e.g. a room named "2024-05-01") and avoids mixing aware/naive datetimes.
"""

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
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    NONE = "none_"


# ---------------------------------------------------------------------------
# Known datetime fields per context.
#
# These are the ONLY fields that get parsed as datetime. Everything else
# stays as str, matching the official SDK's behavior where most timestamp
# fields in list responses are plain strings.
# ---------------------------------------------------------------------------

_DATETIME_KEYS: frozenset[str] = frozenset(
    {
        # User (single-user response)
        "joined_at",
        "last_online_in",
        # Item responses
        "created_at",
        "release_date",
        # Grab responses
        "starts_at",
        "expires_at",
    }
)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _parse_datetime(value: str) -> datetime | str:
    """Parse an ISO-8601 datetime string. Returns the original string on failure."""
    try:
        v = value.replace("Z", "+00:00")
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):
        return value


def _wrap(value: Any) -> Any:
    """Wrap dicts and lists recursively. Does NOT parse datetimes."""
    if isinstance(value, dict):
        return AttrDict(value)

    if isinstance(value, list):
        return [_wrap(v) for v in value]

    return value


def _wrap_with_dates(value: Any) -> Any:
    """Wrap and parse datetime strings. Used only for known datetime keys."""
    if isinstance(value, str):
        return _parse_datetime(value)
    return _wrap(value)


class AttrDict:
    """Dictionary wrapper exposing dict keys as attributes.

    Only fields listed in `_DATETIME_KEYS` are parsed as datetime.
    All other strings pass through unchanged.
    """

    __slots__ = ("_cache", "_raw")

    def __init__(self, raw: dict[str, Any]) -> None:
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_cache", {})

    @property
    def raw(self) -> dict[str, Any]:
        return object.__getattribute__(self, "_raw")

    def _resolve(self, key: str) -> Any:
        cache = object.__getattribute__(self, "_cache")
        if key in cache:
            return cache[key]

        raw = object.__getattribute__(self, "_raw")
        if key not in raw:
            raise KeyError(key)

        value = raw[key]

        # Only parse datetimes for known fields.
        if key in _DATETIME_KEYS and isinstance(value, str):
            result = _parse_datetime(value)
        else:
            result = _wrap(value)

        cache[key] = result
        return result

    def __getattr__(self, name: str) -> Any:
        try:
            return self._resolve(name)
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, key: str) -> Any:
        return self._resolve(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self._resolve(key)
        except KeyError:
            return default

    def __contains__(self, key: str) -> bool:
        return key in object.__getattribute__(self, "_raw")

    def __iter__(self):
        return iter(object.__getattribute__(self, "_raw"))

    def __len__(self) -> int:
        return len(object.__getattribute__(self, "_raw"))

    def __repr__(self) -> str:
        return f"AttrDict({object.__getattribute__(self, '_raw')!r})"


class _Base:
    """Base class for typed-ish WebAPI responses."""

    __slots__ = ("_cache", "_raw")

    def __init__(self, raw: Any) -> None:
        object.__setattr__(self, "_raw", raw if isinstance(raw, dict) else {})
        object.__setattr__(self, "_cache", {})

    @property
    def raw(self) -> dict[str, Any]:
        return object.__getattribute__(self, "_raw")

    def _get(self, key: str, default: Any = None) -> Any:
        cache = object.__getattribute__(self, "_cache")
        if key in cache:
            return cache[key]

        raw = object.__getattribute__(self, "_raw")
        if key in raw:
            val = _wrap(raw[key])
            cache[key] = val
            return val

        return default

    def __getattr__(self, name: str) -> Any:
        cache = object.__getattribute__(self, "_cache")
        if name in cache:
            return cache[name]

        raw = object.__getattribute__(self, "_raw")
        if name in raw:
            val = _wrap(raw[name])
            cache[name] = val
            return val

        raise AttributeError(name)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({object.__getattribute__(self, '_raw')!r})"


class GetPublicUserResponse(_Base):
    @property
    def user(self) -> Any:
        return self._get("user")


class GetPublicUsersResponse(_Base):
    @property
    def users(self) -> Any:
        return self._get("users", [])

    @property
    def total(self) -> int:
        return _as_int(self._raw.get("total"), 0)

    @property
    def first_id(self) -> str:
        return _as_str(self._raw.get("first_id"))

    @property
    def last_id(self) -> str:
        return _as_str(self._raw.get("last_id"))


class GetPublicRoomResponse(_Base):
    @property
    def room(self) -> Any:
        return self._get("room")


class GetPublicRoomsResponse(_Base):
    @property
    def rooms(self) -> Any:
        return self._get("rooms", [])

    @property
    def total(self) -> int:
        return _as_int(self._raw.get("total"), 0)

    @property
    def first_id(self) -> str:
        return _as_str(self._raw.get("first_id"))

    @property
    def last_id(self) -> str:
        return _as_str(self._raw.get("last_id"))


class GetPublicPostResponse(_Base):
    @property
    def post(self) -> Any:
        return self._get("post")


class GetPublicPostsResponse(_Base):
    @property
    def posts(self) -> Any:
        return self._get("posts", [])

    @property
    def total(self) -> int:
        return _as_int(self._raw.get("total"), 0)

    @property
    def first_id(self) -> str:
        return _as_str(self._raw.get("first_id"))

    @property
    def last_id(self) -> str:
        return _as_str(self._raw.get("last_id"))


class GetPublicItemResponse(_Base):
    @property
    def item(self) -> Any:
        return self._get("item")

    @property
    def related_items(self) -> Any:
        return self._get("related_items")

    @property
    def storefront_listings(self) -> Any:
        return self._get("storefront_listings")


class GetPublicItemsResponse(_Base):
    @property
    def items(self) -> Any:
        return self._get("items", [])

    @property
    def total(self) -> int:
        return _as_int(self._raw.get("total"), 0)

    @property
    def first_id(self) -> str:
        return _as_str(self._raw.get("first_id"))

    @property
    def last_id(self) -> str:
        return _as_str(self._raw.get("last_id"))


class GetPublicGrabResponse(_Base):
    @property
    def grab(self) -> Any:
        return self._get("grab")


class GetPublicGrabsResponse(_Base):
    @property
    def grabs(self) -> Any:
        return self._get("grabs", [])

    @property
    def total(self) -> int:
        return _as_int(self._raw.get("total"), 0)

    @property
    def first_id(self) -> str:
        return _as_str(self._raw.get("first_id"))

    @property
    def last_id(self) -> str:
        return _as_str(self._raw.get("last_id"))


def _segments(endpoint: str) -> list[str]:
    path = endpoint.split("?", 1)[0]
    return [part for part in path.strip("/").split("/") if part]


def parse_webapi_response(endpoint: str, data: Any) -> Any:
    """Convert raw WebAPI JSON into a typed-ish response object."""
    if not isinstance(data, dict):
        return data

    parts = _segments(endpoint)

    if not parts:
        return data

    root = parts[0]

    if root == "users":
        if len(parts) > 1:
            return GetPublicUserResponse(data)
        return GetPublicUsersResponse(data)

    if root == "rooms":
        if len(parts) > 1:
            return GetPublicRoomResponse(data)
        return GetPublicRoomsResponse(data)

    if root == "posts":
        if len(parts) > 1:
            return GetPublicPostResponse(data)
        return GetPublicPostsResponse(data)

    if root == "items":
        if len(parts) > 1:
            return GetPublicItemResponse(data)
        return GetPublicItemsResponse(data)

    if root == "grabs":
        if len(parts) > 1:
            return GetPublicGrabResponse(data)
        return GetPublicGrabsResponse(data)

    return data
