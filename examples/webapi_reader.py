"""Reads the public Web API with caching — no bot connection required.

Run:
    python examples/webapi_reader.py USERNAME
"""

from __future__ import annotations

import asyncio
import sys

from highrise_fast import WebAPI


async def main(username: str) -> int:
    # cache_ttl keeps repeated lookups off the network.
    async with _Closing(WebAPI(cache_ttl=60)) as api:
        user_id = await api.username_to_id(username)
        if user_id is None:
            print(f"no user named {username!r}")
            return 1

        user = await api.get_user(user_id)
        print(f"{username} -> {user_id}")
        print(f"  username: {user.user.username}")
        print(f"  followers: {user.user.num_followers}")

        # Second call is served from the TTL cache.
        again = await api.get_user(user_id)
        print(f"  cached repeat ok: {again.user.username == user.user.username}")
    return 0


class _Closing:
    """Closes the WebAPI session even when the body raises."""

    def __init__(self, api: WebAPI) -> None:
        self.api = api

    async def __aenter__(self) -> WebAPI:
        return self.api

    async def __aexit__(self, *exc_info: object) -> None:
        await self.api.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
