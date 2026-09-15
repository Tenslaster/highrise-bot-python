from typing import Any
from collections.abc import Callable

from ...tools.validator import Validator

from ...models.websocket.responses import AcknowledgementResponse, CheckVoiceChatResponse
from ...models.websocket.requests import CheckVoiceChatRequest, InviteSpeakerRequest, RemoveSpeakerRequest

class VoiceMixin:
    """Voice chat-related methods: check status, invite/remove speakers."""

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def get_voice_status(self) -> CheckVoiceChatResponse:
        """Fetches the voice chat status for the room."""

        def build() -> dict:
            request = CheckVoiceChatRequest()
            return request.to_dict()

        return await self._send_request(CheckVoiceChatResponse, build)

    async def add_user_to_voice(self, user_id: str) -> AcknowledgementResponse:
        """Adds a user to voice chat."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")

            request = InviteSpeakerRequest(user_id=user_id)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)

    async def remove_user_from_voice(self, user_id: str) -> AcknowledgementResponse:
        """Removes a user from voice chat."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")

            request = RemoveSpeakerRequest(user_id=user_id)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)