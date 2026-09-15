"""Fast, small JSON codec used by the WebSocket hot path."""
from __future__ import annotations

import json
from typing import Any

try:  # Optional at import time so the SDK remains usable with stdlib JSON.
    import orjson  # type: ignore
except ImportError:  # pragma: no cover
    orjson = None


def dumps(value: Any) -> str | bytes:
    """Serialize compact JSON, preferring orjson when installed."""
    if orjson is not None:
        return orjson.dumps(value)
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def loads(value: str | bytes | bytearray) -> Any:
    """Deserialize JSON, preferring orjson when installed."""
    if orjson is not None:
        return orjson.loads(value)
    return json.loads(value)


FAST_JSON = orjson is not None
