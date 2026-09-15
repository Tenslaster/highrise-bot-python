from dataclasses import dataclass, field
from ..models.websocket.highrise_models import *
from ..models.websocket.responses import GetRoomUsersResponse

@dataclass(slots=True)
class RoomUsersCache:
    """Cached room users, indexed by both user_id and username for fast lookup.
    Each entry maps to a (User, Position | AnchorPosition) tuple.
    """

    _by_id: dict[str, tuple[User, Position | AnchorPosition]] = field(default_factory=dict)
    _by_username: dict[str, tuple[User, Position | AnchorPosition]] = field(default_factory=dict)

    @classmethod
    def _from_response(cls, response: "GetRoomUsersResponse") -> "RoomUsersCache":
        """Builds a cache from an initial GetRoomUsersResponse."""
        cache = cls()
        for user, position in response.content:
            cache._add(user, position)
        return cache

    def _add(self, user: User, position: Position | AnchorPosition) -> None:
        """Adds or overwrites a user's entry."""
        entry = (user, position)
        self._by_id[user.id] = entry
        self._by_username[user.username] = entry

    def _update(self, user_id: str, position: Position | AnchorPosition) -> None:
        """Updates the position for an already-cached user, by user_id.
        No-op if the user isn't cached."""
        existing = self._by_id.get(user_id)
        if existing is None:
            return

        user, _ = existing
        self._add(user, position)

    def _remove(self, identifier: str) -> None:
        """Removes a user's entry, by user_id or username."""
        entry = self._by_id.get(identifier) or self._by_username.get(identifier)
        if entry is None:
            return

        user, _ = entry
        self._by_id.pop(user.id, None)
        self._by_username.pop(user.username, None)

    def find_user(self, identifier: str) -> tuple[User, Position | AnchorPosition] | None:
        """Finds a (user, position) pair by user id or username."""
        return self._by_id.get(identifier) or self._by_username.get(identifier)

    def has_user(self, identifier: str) -> bool:
        """Checks whether a user with the given id or username is cached."""
        return self.find_user(identifier) is not None

    def get_username(self, user_id: str) -> str | None:
        """Returns the username for the given user id, or None if not found."""
        pair = self.find_user(user_id)
        return pair[0].username if pair else None

    def get_user_id(self, username: str) -> str | None:
        """Returns the user id for the given username, or None if not found."""
        pair = self.find_user(username)
        return pair[0].id if pair else None

    def get_position(self, identifier: str) -> Position | AnchorPosition | None:
        """Returns the position for the given user id or username, or None if not found."""
        pair = self.find_user(identifier)
        return pair[1] if pair else None

    def get_all(self) -> list[tuple[User, Position | AnchorPosition]]:
        """Returns all cached (user, position) pairs."""
        return list(self._by_id.values())

    def users_count(self) -> int:
        """Returns the number of cached users."""
        return len(self._by_id)

    def clear(self) -> None:
        """Clears the cache."""
        self._by_id.clear()
        self._by_username.clear()