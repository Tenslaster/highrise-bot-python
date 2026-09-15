from typing import Any
from collections.abc import Callable

from ...tools.validator import Validator

from ...models.websocket.responses import AcknowledgementResponse
from ...models.websocket.requests import ChannelRequest


class ChannelMixin:
    """Hidden channel methods: bot-to-bot or bot-to-client communication."""

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def send_channel(
        self,
        message: str,
        tags: list[str] | None = None,
    ) -> AcknowledgementResponse:
        """Sends a hidden channel message to the room for bot-to-bot or bot-to-client communication."""

        def build() -> dict:
            Validator.required(message, "message")
            Validator.string(message, "message")

            tag_list = tags if tags is not None else []

            request = ChannelRequest(message=message, tags=tag_list)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)