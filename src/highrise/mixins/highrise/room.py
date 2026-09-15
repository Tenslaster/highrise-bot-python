from typing import Any
from collections.abc import Callable

from ...tools.validator import Validator

from ...models.websocket.responses import GetRoomUsersResponse, GetRoomPrivilegeResponse, AcknowledgementResponse
from ...models.websocket.requests import GetRoomUsersRequest, GetRoomPrivilegeRequest, ChangeRoomPrivilegeRequest
from ...models.websocket.highrise_models import RoomPermissions

class RoomMixin:
    """Room-related methods: fetch users currently in the room."""

    async def _send_request(self, response_cls: Any, build_payload: Callable[[], dict]) -> Any: ...

    async def get_room_users(self) -> GetRoomUsersResponse:
        """Fetches the list of users currently in the room, with their positions."""

        def build() -> dict:
            request = GetRoomUsersRequest()
            return request.to_dict()

        return await self._send_request(GetRoomUsersResponse, build)

    async def get_room_privilege(self, user_id: str) -> GetRoomPrivilegeResponse:
        """Fetches the room privilege for the given user."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")

            request = GetRoomPrivilegeRequest(user_id=user_id)
            return request.to_dict()

        return await self._send_request(GetRoomPrivilegeResponse, build)

    async def is_moderator(self, user_id: str) -> bool:
        """Checks whether the given user has moderator privileges.

        Uses `get_room_privilege` internally.
        """
        response = await self.get_room_privilege(user_id)
        return response.ok and bool(response.moderator)

    async def is_designer(self, user_id: str) -> bool:
        """Checks whether the given user has designer privileges.

        Uses `get_room_privilege` internally.
        """
        response = await self.get_room_privilege(user_id)
        return response.ok and bool(response.designer)

    async def change_room_privilege(
        self, user_id: str, permissions: RoomPermissions
    ) -> AcknowledgementResponse:
        """Change the room privilege for the given user."""

        def build() -> dict:
            Validator.required(user_id, "user_id")
            Validator.string(user_id, "user_id")
            Validator.required(permissions, "permissions")

            if permissions.moderator is not None:
                Validator.boolean(permissions.moderator, "permissions.moderator")
            if permissions.designer is not None:
                Validator.boolean(permissions.designer, "permissions.designer")

            request = ChangeRoomPrivilegeRequest(user_id=user_id, permissions=permissions)
            return request.to_dict()

        return await self._send_request(AcknowledgementResponse, build)

    async def add_moderator(self, user_id: str) -> AcknowledgementResponse:
        """Grants moderator privileges to the given user.

        Uses `change_room_privilege` internally.
        """
        return await self.change_room_privilege(user_id, RoomPermissions(moderator=True))

    async def remove_moderator(self, user_id: str) -> AcknowledgementResponse:
        """Revokes moderator privileges from the given user.

        Uses `change_room_privilege` internally.
        """
        return await self.change_room_privilege(user_id, RoomPermissions(moderator=False))

    async def add_designer(self, user_id: str) -> AcknowledgementResponse:
        """Grants designer privileges to the given user.

        Uses `change_room_privilege` internally.
        """
        return await self.change_room_privilege(user_id, RoomPermissions(designer=True))

    async def remove_designer(self, user_id: str) -> AcknowledgementResponse:
        """Revokes designer privileges from the given user.

        Uses `change_room_privilege` internally.
        """
        return await self.change_room_privilege(user_id, RoomPermissions(designer=False))