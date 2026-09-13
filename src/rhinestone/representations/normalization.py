"""Normalization functions for shared representation definitions."""

from typing import Any, Optional

from .definitions import CONTAINER_MEDIA_TYPES, FORMAT_ALIASES, MEDIA_TYPE_FORMATS


def canonical_format(value: Any) -> Optional[str]:
    """Return a canonical format name without inferring from a URI suffix."""

    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return FORMAT_ALIASES.get(normalized, normalized)


def format_from_media_type(value: Any) -> Optional[str]:
    """Return the known canonical format for a media type."""

    if not isinstance(value, str):
        return None
    media_type = value.strip().lower().split(";", 1)[0].strip()
    if not media_type:
        return None
    return MEDIA_TYPE_FORMATS.get(media_type)


def container_from_media_type(value: Any) -> Optional[str]:
    """Return container evidence without treating it as a payload format."""

    if not isinstance(value, str):
        return None
    media_type = value.strip().lower().split(";", 1)[0].strip()
    if not media_type:
        return None
    return CONTAINER_MEDIA_TYPES.get(media_type)


__all__ = [
    "canonical_format",
    "container_from_media_type",
    "format_from_media_type",
]
