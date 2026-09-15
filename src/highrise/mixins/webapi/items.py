from typing import Any
from collections.abc import Callable

from ...models.webapi.webapi_models import SortOptions, ItemCategory, Rarity

from ...tools.validator import Validator

from ...models.webapi.responses import SearchItemsResponse, GetPublicItemResponse, GetPublicItemsResponse

class ItemsWebMixin:
    """Public web API methods for item search."""

    async def _send_request(
        self, endpoint: str, response_cls: Any, validate_fn: Callable, params: dict | None = None
    ) -> Any: ...

    async def search_items(
        self,
        query: str,
        limit: int | None = None,
        skip: int | None = None,
    ) -> SearchItemsResponse:
        """Search for items by name/query. `skip` offsets results for
        pagination, omit it to start from the beginning.

        Page sizes are not constant, this endpoint may return a final
        page with fewer items than requested, or an empty page before
        pagination stops. When iterating with `async for-in`, always check
        `if page.items:` before indexing, since the last page yielded
        may be empty.
        """

        def validate():
            Validator.required(query, 'query')
            Validator.string(query, 'query')
            if limit is not None:
                Validator.range(limit, 1, 100, "limit")
            if skip is not None:
                Validator.integer(skip, 'skip')
                Validator.range(skip, 0, 100_000, "skip")

        params = {
            "limit": limit,
            "query": query,
            "skip": skip,
        }

        params = {k: v for k, v in params.items() if v is not None}

        response = await self._send_request("/items/search", SearchItemsResponse, validate, params=params)

        if response.ok and response.items:
            next_skip = (skip or 0) + len(response.items)
            response.next_page_fn = lambda: self.search_items(
                query=query, limit=limit, skip=next_skip,
            )

        return response

    async def get_item(self, item_id: str) -> GetPublicItemResponse:
        """Fetch a single item given its `item_id`."""

        def validate():
            Validator.required(item_id, "item_id")
            Validator.string(item_id, "item_id")

        return await self._send_request(f"/items/{item_id}", GetPublicItemResponse, validate)

    async def get_items(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: SortOptions = "desc",
        limit: int = 20,
        rarity: str | None = None,
        item_name: str | None = None,
        category: ItemCategory | None = None,
    ) -> GetPublicItemsResponse:
        """Fetch a list of items, can be filtered, ordered, and paginated.
            - `rarity`: The rarities of items to filter for, comma separated for multiple rarities (eg: `"rare,epic,legendary,none"`) or just one `"rare"`."""

        def validate():
            Validator.string(sort_order, "sort_order")
            Validator.one_of(sort_order, ("desc", "asc"), "sort_order")

            Validator.integer(limit, "limit")
            Validator.range(limit, 1, 100, "limit")

            if starts_after is not None:
                Validator.string(starts_after, "starts_after")

            if ends_before is not None:
                Validator.string(ends_before, "ends_before")

            if rarity is not None:
                Validator.string(rarity, "rarity")
                valid_rarities = {r.value for r in Rarity}

                for r in rarity.split(","):
                    Validator.one_of(r.strip(), valid_rarities, "rarity")

            if item_name is not None:
                Validator.string(item_name, "item_name")

        params = {
            "starts_after": starts_after,
            "ends_before": ends_before,
            "sort_order": sort_order,
            "limit": limit,
            "rarity": rarity,
            "item_name": item_name,
            "category": category.value if category is not None else None,
        }

        params = {k: v for k, v in params.items() if v is not None}

        response = await self._send_request("/items", GetPublicItemsResponse, validate, params=params)

        if response.ok and len(response.items) == limit:
            last_id = response.last_id
            response.next_page_fn = lambda: self.get_items(
                starts_after=last_id, sort_order=sort_order, limit=limit,
                rarity=rarity, item_name=item_name, category=category,
            )

        return response