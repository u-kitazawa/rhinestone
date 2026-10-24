"""Parsing helpers for search.ckan.jp package responses."""

from collections.abc import Mapping
from typing import Any, cast

from ....representations import canonical_format, format_from_media_type
from ..base import JsonObject


def optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def resource_format(resource: JsonObject) -> str | None:
    format_name = optional_string(resource.get("format"))
    if format_name is not None and format_name.strip():
        return canonical_format(format_name)
    media_type = optional_string(resource.get("mimetype"))
    return format_from_media_type(media_type)


def organization_title(value: Any) -> str | None:
    if isinstance(value, Mapping):
        organization = cast(Mapping[str, Any], value)
        title = organization.get("title")
        return title if isinstance(title, str) else None
    return None
