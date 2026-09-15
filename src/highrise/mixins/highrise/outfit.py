from typing import TYPE_CHECKING, Any
from collections.abc import Callable

from ...tools.validator import Validator

if TYPE_CHECKING:
    from ...base_bot import BotContext

from ...models.websocket.responses import GetUserOutfitResponse, AcknowledgementResponse
from ...models.websocket.requests import GetUserOutfitRequest, SetOutfitRequest

from ...models.websocket.highrise_models import OutfitItem
from ...constants import DEFAULT_OUTFIT

class OutfitMixin:
    """Bot outfit-related methods: get and set the bot's own outfit."""

    _context: "BotContext"
    _body_flesh_item = OutfitItem(type='clothing', amount=1, id='body-flesh', account_bound=False, active_palette=0)

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def get_my_outfit(self) -> GetUserOutfitResponse:
        """Fetches the bot's own outfit."""

        outfit = self._context.cache.outfit.get("outfit")
        if outfit is not None:
            return outfit

        if self._context.session_metadata is None:
            return GetUserOutfitResponse._from_raw(
                success=False,
                data="Bot is not connected yet (self.session_metadata is None)."
            )

        def build() -> dict:
            request = GetUserOutfitRequest(user_id=self._context.session_metadata.user_id)
            return request.to_dict()

        response = await self._send_request(GetUserOutfitResponse, build)
        if response.ok:
            self._context.cache.outfit.set("outfit", response)

        return response

    async def set_outfit(self, outfit: list[OutfitItem] | None = None) -> AcknowledgementResponse:
        """Sets the bot's outfit. Automatically ensures the base `body-flesh` item is present."""

        target_outfit = outfit if outfit is not None else list(DEFAULT_OUTFIT)

        has_flesh = any(item.id == self._body_flesh_item.id for item in target_outfit)
        final_outfit = target_outfit if has_flesh else [self._body_flesh_item] + target_outfit


        def build() -> dict:
            Validator.required(final_outfit, "outfit")

            for item in final_outfit:
                Validator.instance_of(item, OutfitItem, "outfit items")

            request = SetOutfitRequest(outfit=final_outfit)
            return request.to_dict()

        response = await self._send_request(AcknowledgementResponse, build)

        if response.ok:
            self._context.cache.outfit.set(
                "outfit",
                GetUserOutfitResponse(ok=True, error=None, outfit=final_outfit, count=len(final_outfit)),
            )

        return response

    async def change_item_color(self, item_id: str, palette_index: int) -> AcknowledgementResponse:
        """Changes the active palette of an item currently in the bot's outfit."""

        Validator.required(item_id, "item_id").string(item_id, "item_id")
        Validator.required(palette_index, "palette_index").integer(palette_index, "palette_index")

        current = await self.get_my_outfit()
        if not current.ok:
            return AcknowledgementResponse(ok=False, error=current.error)

        target_item = None
        for item in current.outfit:
            if item.id == item_id:
                target_item = item
                break

        if target_item is None:
            return AcknowledgementResponse(ok=False, error=f"Item not found: {item_id}")

        new_outfit = [
            OutfitItem(
                type=item.type,
                amount=item.amount,
                id=item.id,
                account_bound=item.account_bound,
                active_palette=palette_index if item.id == item_id else item.active_palette,
            ) for item in current.outfit
        ]

        return await self.set_outfit(new_outfit)

    async def add_outfit_item(self, item: OutfitItem) -> AcknowledgementResponse:
        """Adds a new item to the bot's outfit."""

        Validator.required(item, "item").instance_of(item, OutfitItem, 'item')

        current = await self.get_my_outfit()
        if not current.ok:
            return AcknowledgementResponse(ok=False, error=current.error)

        if any(existing.id == item.id for existing in current.outfit):
            return AcknowledgementResponse(ok=False, error=f"Item already in outfit: {item.id}")

        new_outfit = current.outfit + [item]

        return await self.set_outfit(new_outfit)


    async def remove_outfit_item(self, item_id: str) -> AcknowledgementResponse:
        """Removes an item from the bot's outfit."""

        Validator.required(item_id, "item_id").string(item_id, 'item_id')

        current = await self.get_my_outfit()
        if not current.ok:
            return AcknowledgementResponse(ok=False, error=current.error)

        if not any(existing.id == item_id for existing in current.outfit):
            return AcknowledgementResponse(ok=False, error=f"Item not found: {item_id}")

        new_outfit = [existing for existing in current.outfit if existing.id != item_id]

        return await self.set_outfit(new_outfit)