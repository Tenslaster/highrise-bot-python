from typing import Any
from collections.abc import Callable

from ...models.websocket.responses import GetWalletResponse
from ...models.websocket.requests import GetWalletRequest

class WalletMixin:
    """Wallet-related methods: fetch the bot's currency balances."""

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def get_wallet(self) -> GetWalletResponse:
        """Fetches the bot's wallet."""

        def build() -> dict:
            request = GetWalletRequest()
            return request.to_dict()

        return await self._send_request(GetWalletResponse, build)