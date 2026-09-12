"""Compatibility exports for CKAN format helpers."""

from typing import Any, Optional

from ....representations import canonical_format


def optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


__all__ = ["canonical_format"]
