from __future__ import annotations

import httpx
from .constants import WEBAPI_BASE_URL
from typing import Any, TYPE_CHECKING
from collections.abc import Callable

from .mixins.webapi.users import UsersWebMixin
from .mixins.webapi.rooms import RoomsWebMixin
from .mixins.webapi.posts import PostsWebMixin
from .mixins.webapi.items import ItemsWebMixin
from .mixins.webapi.grabs import GrabsWebMixin

if TYPE_CHECKING:
    from .core.bot_context import BotContext


class WebApi(
    UsersWebMixin,
    RoomsWebMixin,
    ItemsWebMixin,
    PostsWebMixin,
    GrabsWebMixin,
):
    """Asynchronous Highrise Web API client with explicit lifecycle."""

    def __init__(self, context: "BotContext", base_url: str = WEBAPI_BASE_URL) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(10.0),
            follow_redirects=False,
            headers={"Accept": "application/json"},
        )
        self._context = context
        self._closed = False

    def reopen(self) -> None:
        """Re-open the HTTP client after a previous full bot shutdown."""
        if not self._closed:
            return
        self._client = httpx.AsyncClient(
            base_url=str(self._client.base_url),
            timeout=httpx.Timeout(10.0),
            follow_redirects=False,
            headers={"Accept": "application/json"},
        )
        self._closed = False

    async def _send_request(
        self,
        endpoint: str,
        response_cls: Any,
        validate_fn: Callable,
        params: dict | None = None,
    ) -> Any:
        if self._closed:
            return response_cls._from_raw(False, "Web API client is closed.")

        try:
            validate_fn()
            resp = await self._client.get(endpoint, params=params)
        except (httpx.RequestError, ValueError) as exc:
            return response_cls._from_raw(False, str(exc))

        if 200 <= resp.status_code < 300:
            try:
                payload = resp.json()
            except ValueError as exc:
                return response_cls._from_raw(False, f"Invalid JSON response: {exc}")
            return response_cls._from_raw(True, payload)

        return response_cls._from_raw(False, resp.text[:4096])

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._client.aclose()

    async def close(self) -> None:
        """Alias for aclose()."""
        await self.aclose()
