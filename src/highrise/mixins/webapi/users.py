from ...models.webapi.responses import GetPublicUserResponse
from typing import Any
from collections.abc import Callable

from ...tools.validator import Validator

class UsersWebMixin:
    """Public web API methods for user lookups."""

    async def _send_request(
        self, endpoint: str, response_cls: Any, validate_fn: Callable, params: dict | None = None
    ) -> Any: ...

    async def get_user(self, identifier: str) -> GetPublicUserResponse:
        """Fetches a user's public profile by id or username."""
        
        def validate():
            Validator.required(identifier, "identifier")
            Validator.string(identifier, "identifier")

        return await self._send_request(f"/users/{identifier}", GetPublicUserResponse, validate)