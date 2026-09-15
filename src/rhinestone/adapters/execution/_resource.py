"""Shared helpers for selected execution adapters."""

from collections.abc import Mapping
from typing import Any

from ...models import Resource


def resource_attributes(resource: Resource) -> Mapping[str, Any]:
    for candidate in resource.source.candidates:
        if candidate.uri == resource.uri and candidate.attributes.get(
            "matches_config", True
        ):
            return candidate.attributes
    return {}
