from dataclasses import dataclass
from typing import Any


@dataclass
class BaseResponse:
    """Base class for all WebSocket request/response results.

    every typed response (chat ack, room data, inventory, etc.) builds on this
    shared ok/error contract.
    """
    ok: bool
    error: str | None = None

    @classmethod
    def _from_raw(cls, success: bool, data: Any) -> "BaseResponse":
        """Constructs a response from a WSRequester.send() result.

        Subclasses override build() to populate their own fields
        from `data` when `success` is True.
        """
        instance = cls(ok=success)

        if not success:
            instance.error = data if isinstance(data, str) else str(data)
            return instance

        try:
            instance._build(data)
        except Exception as e:
            instance.ok = False
            instance.error = f"Failed to parse response: {e}"

        return instance

    def _build(self, data: Any) -> None:
        """Override in subclasses to populate fields from a
        successful response payload. No-op by default."""
        pass

    def has_error(self) -> bool:
        return not self.ok