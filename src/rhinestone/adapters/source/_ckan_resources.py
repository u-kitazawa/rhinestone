"""Validate CKAN search distributions without losing valid sibling resources."""

from collections.abc import Mapping
from typing import Any, cast

from ...errors import ProviderResponseError
from ...models import SearchDiagnostic
from .base import JsonObject


def resource_objects(
    value: Any, source_id: str, diagnostics: list[SearchDiagnostic]
) -> tuple[JsonObject, ...]:
    """Reject broken containers and diagnose individual non-object members."""
    if isinstance(value, Mapping):
        return (cast(JsonObject, value),)
    if not isinstance(value, list):
        raise ProviderResponseError("CKAN resources must be an object or array")
    found: list[JsonObject] = []
    for item in cast(list[Any], value):
        if isinstance(item, Mapping):
            found.append(cast(JsonObject, item))
        else:
            diagnostics.append(
                SearchDiagnostic(
                    source_id=source_id,
                    skipped_conditions=frozenset(),
                    reason="item_skipped",
                    detail="invalid_resource",
                )
            )
    return tuple(found)


def package_objects(
    value: Any, source_id: str, diagnostics: list[SearchDiagnostic]
) -> tuple[JsonObject | None, ...]:
    """Keep invalid slots so pagination counts all received packages."""
    if isinstance(value, Mapping):
        return (cast(JsonObject, value),)
    if not isinstance(value, list):
        raise ProviderResponseError("CKAN packages must be an object or array")
    found: list[JsonObject | None] = []
    for item in cast(list[Any], value):
        if isinstance(item, Mapping):
            found.append(cast(JsonObject, item))
        else:
            found.append(None)
            diagnostics.append(
                SearchDiagnostic(
                    source_id=source_id,
                    skipped_conditions=frozenset(),
                    reason="item_skipped",
                    detail="invalid_dataset",
                )
            )
    return tuple(found)
