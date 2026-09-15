from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from ...tools.validator import Validator

from ...models.websocket.responses import BuyItemResponse, GetInventoryResponse
from ...models.websocket.requests import BuyItemRequest, GetInventoryRequest

class InventoryMixin:
    """Inventory-related methods: buy items."""

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def buy_item(self, item_id: str) -> BuyItemResponse:
        """Buys an item."""

        def build() -> dict:
            Validator.required(item_id, "item_id")
            Validator.string(item_id, "item_id")

            request = BuyItemRequest(item_id=item_id)
            return request.to_dict()

        return await self._send_request(BuyItemResponse, build)

    async def get_inventory(self) -> GetInventoryResponse:
        """Fetches the bot's inventory."""

        def build() -> dict:
            request = GetInventoryRequest()
            return request.to_dict()

        return await self._send_request(GetInventoryResponse, build)