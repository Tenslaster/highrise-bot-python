"""Highrise Web API client with typed public responses and connection pooling."""

from typing import Any, Literal

from cattrs import Converter
from highrise_fast import WebAPI as _WebAPI
from highrise_fast._pycompat import StrEnum
from highrise_fast.models_webapi import SearchItemsResponse, webapi_response_type
from pendulum import DateTime, parse

from . import models_webapi

SORT_OPTION = Literal["desc", "asc"]
converter = Converter()


def _parse_datetime(value: str, _) -> DateTime:
    return parse(value)


def _parse_skin_part(data: dict[str, Any], _) -> models_webapi.SkinPart:
    return models_webapi.SkinPart(
        bone=data.get("bone", ""),
        slot=data.get("slot", ""),
        image_file=data.get("image_file", data.get("imageFile", "")),
        attachment_name=data.get("attachment_name", data.get("attachmentName")),
        has_remote_render_layer=data.get(
            "has_remote_render_layer", data.get("hasRemoteRenderLayer")
        ),
    )


def _parse_enum(value: str, cls: type[StrEnum]) -> StrEnum:
    """Keep new server enum values readable by older bots."""
    try:
        return cls(value)
    except ValueError:
        if not isinstance(value, str):
            raise
        member = str.__new__(cls, value)
        member._name_ = value.upper()
        member._value_ = value
        return member


converter.register_structure_hook(DateTime, _parse_datetime)
converter.register_structure_hook(models_webapi.SkinPart, _parse_skin_part)
for _enum_type in (
    models_webapi.ItemCategory,
    models_webapi.Rarity,
    models_webapi.LegacyRewardCategory,
    models_webapi.NFIStrategy,
):
    converter.register_structure_hook(_enum_type, _parse_enum)


class WebAPI(_WebAPI):
    """Cached Web API client that returns the standard Highrise model classes."""

    @staticmethod
    def _response_type(endpoint: str) -> type | None:
        model = webapi_response_type(endpoint)
        return getattr(models_webapi, model.__name__) if model is not None else None

    @staticmethod
    def _structure_response(data: Any, cl: type | None) -> Any:
        if cl is SearchItemsResponse:
            return SearchItemsResponse(data)
        return converter.structure(data, cl) if cl is not None else data
