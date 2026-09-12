"""Parsing helpers for search.ckan.jp package responses."""

from typing import Any, Mapping, Optional, cast

from ..base import JsonObject
from ..ckan.format import canonical_format

_MEDIA_TYPE_FORMATS = {
    "application/geo+json": "geojson",
    "application/geopackage+sqlite3": "gpkg",
    "application/json": "json",
    "application/zip": "zip",
    "text/csv": "csv",
}


def optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def resource_format(resource: JsonObject) -> Optional[str]:
    format_name = optional_string(resource.get("format"))
    if format_name is not None and format_name.strip():
        return canonical_format(format_name)
    media_type = optional_string(resource.get("mimetype"))
    return _MEDIA_TYPE_FORMATS.get(media_type or "")


def organization_title(value: Any) -> Optional[str]:
    if isinstance(value, Mapping):
        organization = cast(Mapping[str, Any], value)
        title = organization.get("title")
        return title if isinstance(title, str) else None
    return None
