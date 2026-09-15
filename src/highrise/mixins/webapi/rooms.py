from ...models.webapi.responses import GetPublicRoomResponse, GetPublicRoomsResponse
from typing import Any
from collections.abc import Callable
from ...models.webapi.webapi_models import SortOptions

from ...tools.validator import Validator

class RoomsWebMixin:
    """Public web API methods for room lookups."""

    async def _send_request(
        self, endpoint: str, response_cls: Any, validate_fn: Callable, params: dict | None = None
    ) -> Any: ...

    async def get_room(self, room_id: str) -> GetPublicRoomResponse:
        """Fetch a single room given its room_id."""

        def validate():
            Validator.required(room_id, "room_id")
            Validator.string(room_id, "room_id")

        return await self._send_request(f"/rooms/{room_id}", GetPublicRoomResponse, validate)

    async def get_rooms(
        self,
        starts_after: str | None = None,
        ends_before: str | None = None,
        room_name: str | None = None,
        owner_id: str | None = None,
        sort_order: SortOptions = "desc",
        limit: int = 20,
    ) -> GetPublicRoomsResponse:
        """Fetch a list of rooms, filtered, ordered, and paginated."""

        def validate():
            if starts_after: Validator.string(starts_after, 'starts_after')
            if ends_before: Validator.string(ends_before, 'ends_before')
            if room_name: Validator.string(room_name, 'room_name')
            if owner_id: Validator.string(owner_id, 'owner_id')
            
            Validator.one_of(sort_order, ("desc", "asc"), "sort_order")
            Validator.range(limit, 1, 100, "limit")

        params = {
            "starts_after": starts_after,
            "ends_before": ends_before,
            "sort_order": sort_order,
            "limit": limit,
            "room_name": room_name,
            "owner_id": owner_id,
        }
        
        params = {k: v for k, v in params.items() if v is not None}

        response = await self._send_request('/rooms', GetPublicRoomsResponse, validate, params)

        if response.ok and len(response.rooms) == limit:
            last_id = response.last_id
            response.next_page_fn = lambda: self.get_rooms(
                starts_after=last_id, sort_order=sort_order, limit=limit,
                room_name=room_name, owner_id=owner_id,
            )

        return response