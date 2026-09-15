from typing import Any
from collections.abc import Callable

from ...models.webapi.webapi_models import SortOptions
from ...tools.validator import Validator

from ...models.webapi.responses import GetPublicGrabResponse, GetPublicGrabsResponse

class GrabsWebMixin:
    """Public web API methods for grab lookups."""

    async def _send_request(
        self, endpoint: str, response_cls: Any, validate_fn: Callable, params: dict | None = None
    ) -> Any: ...

    async def get_grab(self, grab_id: str) -> GetPublicGrabResponse:
        """Fetch a single grab given its grab_id."""

        def validate():
            Validator.required(grab_id, "grab_id")
            Validator.string(grab_id, "grab_id")

        return await self._send_request(f"/grabs/{grab_id}", GetPublicGrabResponse, validate)

    async def get_grabs(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: SortOptions = "desc",
        limit: int = 20,
        title: str | None = None,
    ) -> GetPublicGrabsResponse:
        """Fetch a list of grabs, can be filtered, ordered, and paginated."""

        def validate():
            Validator.string(sort_order, "sort_order")
            Validator.one_of(sort_order, ("desc", "asc"), "sort_order")

            Validator.integer(limit, "limit")
            Validator.range(limit, 1, 100, "limit")

            if starts_after is not None:
                Validator.string(starts_after, "starts_after")
            if ends_before is not None:
                Validator.string(ends_before, "ends_before")
            if title is not None:
                Validator.string(title, "title")

        params = {
            "starts_after": starts_after,
            "ends_before": ends_before,
            "sort_order": sort_order,
            "limit": limit,
            "title": title,
        }
        params = {k: v for k, v in params.items() if v is not None}

        response = await self._send_request("/grabs", GetPublicGrabsResponse, validate, params=params)

        if response.ok and len(response.grabs) == limit:
            last_id = response.last_id
            response.next_page_fn = lambda: self.get_grabs(
                starts_after=last_id, sort_order=sort_order, limit=limit, title=title,
            )

        return response