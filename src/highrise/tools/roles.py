import json
import os
import tempfile
from pathlib import Path
import atexit
from collections.abc import Iterable

class Roles:
    """Manages named roles and their assigned user ids, with auto save/load
    to a local `JSON` file. Loads synchronously on construction, saving
    happens periodically via a background task started by `BaseBot`."""

    __slots__ = ("path", "roles")

    def __init__(self, path: str | Path = "./jsons/roles.json") -> None:
        self.path = Path(path)
        self.roles: dict[str, set[str]] = {"mod": set(), "owner": set()}
        self._load()
        atexit.register(self.save)

    def _load(self) -> None:
        """Loads roles from disk, if the file exists. Creates the
        parent directory if it doesn't exist yet. Silently starts
        from defaults if the file is missing or unreadable."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.save()
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        if not isinstance(raw, dict):
            return

        validated: dict[str, set[str]] = {}
        for role, user_ids in raw.items():
            if not isinstance(role, str) or not isinstance(user_ids, list):
                continue
            clean_ids = {uid for uid in user_ids if isinstance(uid, str) and uid}
            validated[role] = clean_ids

        self.roles = validated
        self.roles.setdefault("mod", set())
        self.roles.setdefault("owner", set())

    def save(self) -> None:
        """Saves roles to disk atomically: writes to a temp file in the
        same directory, then replaces the target file in one step, so
        a crash mid-write never corrupts the existing file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        serializable = {role: sorted(user_ids) for role, user_ids in self.roles.items()}

        fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            # Clean up the temp file without masking the original exception.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def add_role(self, role: str, user_id: str) -> None:
        """Adds a role if it doesn't exist, then assigns it to the given user."""
        self.roles.setdefault(role, set()).add(user_id)

    def remove_role(self, role: str, user_id: str) -> None:
        """Removes a user from a role. No-op if the user or role isn't present."""
        if role in self.roles:
            self.roles[role].discard(user_id)

    def has_role(self, user_id: str, role: str) -> bool:
        """Checks whether a user has the given role."""
        return user_id in self.roles.get(role, set())

    def has_any_role(self, user_id: str, roles: Iterable[str]) -> bool:
        """Checks whether a user has at least one of the given roles."""
        return any(self.has_role(user_id, role) for role in roles)

    def has_all_roles(self, user_id: str, roles: Iterable[str]) -> bool:
        """Checks whether a user has every one of the given roles."""
        return all(self.has_role(user_id, role) for role in roles)

    def get_roles(self, user_id: str) -> list[str]:
        """Returns every role assigned to the given user."""
        return [role for role, users in self.roles.items() if user_id in users]

    def get_users(self, role: str) -> list[str]:
        """Returns every user id assigned to the given role."""
        return list(self.roles.get(role, set()))

    def is_mod(self, user_id: str) -> bool:
        """Checks whether a user has the 'mod' role."""
        return self.has_role(user_id, "mod")

    def is_owner(self, user_id: str) -> bool:
        """Checks whether a user has the 'owner' role."""
        return self.has_role(user_id, "owner")

    def delete_role(self, role: str) -> None:
        """Removes an entire role and every user assigned to it."""
        self.roles.pop(role, None)

    def list_roles(self) -> list[str]:
        """Returns every role name currently defined."""
        return list(self.roles.keys())