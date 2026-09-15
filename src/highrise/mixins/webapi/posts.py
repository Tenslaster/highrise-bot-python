from ...models.webapi.responses import GetPublicPostResponse, GetPublicPostsResponse
from typing import Any
from collections.abc import Callable

from ...models.webapi.webapi_models import SortOptions

from ...tools.validator import Validator

class PostsWebMixin:
    """Public web API methods for post lookups."""
    async def _send_request(
        self, endpoint: str, response_cls: Any, validate_fn: Callable, params: dict | None = None
    ) -> Any: ...

    async def get_post(self, post_id: str) -> GetPublicPostResponse:
        """Fetch a single post given its post_id."""

        def validate(): 
            Validator.required(post_id, 'post_id')
            Validator.string(post_id, 'post_id')

        return await self._send_request(f"/posts/{post_id}", GetPublicPostResponse, validate)

    async def get_posts(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        sort_order: SortOptions = "desc",
        limit: int = 20,
        author_id: str | None = None,
    ) -> GetPublicPostsResponse:
        """Fetch a list of posts, filtered, ordered, and paginated."""

        def validate():
            Validator.one_of(sort_order, ("desc", "asc"), "sort_order")
            Validator.range(limit, 1, 100, "limit")

        params = {
            "starts_after": starts_after,
            "ends_before": ends_before,
            "sort_order": sort_order,
            "limit": limit,
            "author_id": author_id,
        }

        params = {k: v for k, v in params.items() if v is not None}

        response = await self._send_request('/posts', GetPublicPostsResponse, validate, params)

        if response.ok and len(response.posts) == limit:
            last_id = response.last_id
            response.next_page_fn = lambda: self.get_posts(
                starts_after=last_id, sort_order=sort_order, limit=limit, author_id=author_id,
            )

        return response