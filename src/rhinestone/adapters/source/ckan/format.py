"""CKAN resource format and scalar value normalization."""

from typing import Any, Optional

_FORMAT_ALIASES = {"geopackage": "gpkg"}


def optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def canonical_format(value: Any) -> Optional[str]:
    format_name = optional_string(value)
    if format_name is None:
        return None
    normalized = format_name.strip().lower()
    return _FORMAT_ALIASES.get(normalized, normalized)


__all__ = ["canonical_format"]
