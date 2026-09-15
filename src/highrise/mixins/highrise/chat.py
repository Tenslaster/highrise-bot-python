from typing import Any
from collections.abc import Callable
import asyncio
import textwrap

from ...tools.validator import Validator

from ...models.websocket.responses import AcknowledgementResponse
from ...models.websocket.requests import ChatRequest

MAX_MESSAGE_LENGTH = 256
SPLIT_DELAY = 0.4


class ChatMixin:
    """Chat-related methods: room chat, whispers."""

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def _send_chunks(self, chunks: list[str], build_request: Callable[[str], Any]) -> list[AcknowledgementResponse]:
        """Sends each chunk in order with a delay between sends, collecting all responses."""
        responses: list[AcknowledgementResponse] = []

        for i, chunk in enumerate(chunks):
            def build(chunk=chunk) -> dict:
                request = build_request(chunk)
                return request.to_dict()

            response = await self._send_request(AcknowledgementResponse, build)
            responses.append(response)

            if i < len(chunks) - 1:
                await asyncio.sleep(SPLIT_DELAY)

        return responses

    async def chat(self, message: str) -> AcknowledgementResponse | list[AcknowledgementResponse]:
        """Sends a message to the room's chat. Messages over `256` characters
        are automatically split into multiple chunks, sent with a `400ms`
        delay between each. Returns a single response normally, or a list
        of responses if the message was split."""
        Validator.required(message, "message")
        Validator.string(message, "message")

        if len(message) <= MAX_MESSAGE_LENGTH:
            def build() -> dict:
                request = ChatRequest(message=message)
                return request.to_dict()

            return await self._send_request(AcknowledgementResponse, build)

        chunks = textwrap.wrap(message, width=MAX_MESSAGE_LENGTH)
        return await self._send_chunks(chunks, lambda chunk: ChatRequest(message=chunk))

    async def send_whisper(self, user_id: str, message: str) -> AcknowledgementResponse | list[AcknowledgementResponse]:
        """Sends a whisper to a user in the room's chat. Messages over `256`
        characters are automatically split into multiple chunks, sent with
        a `400ms` delay between each. Returns a single response normally, or
        a list of responses if the message was split."""
        Validator.required(user_id, "user_id")
        Validator.string(user_id, "user_id")
        Validator.required(message, "message")
        Validator.string(message, "message")

        if len(message) <= MAX_MESSAGE_LENGTH:
            def build() -> dict:
                request = ChatRequest(message=message, whisper_target_id=user_id)
                return request.to_dict()

            return await self._send_request(AcknowledgementResponse, build)

        chunks = textwrap.wrap(message, width=MAX_MESSAGE_LENGTH)
        return await self._send_chunks(chunks, lambda chunk: ChatRequest(message=chunk, whisper_target_id=user_id))