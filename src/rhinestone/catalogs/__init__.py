"""Repository-managed Source Catalog loading."""

import json
from importlib import resources
from typing import Any, List, Mapping, Tuple, cast

from ..errors import ConfigValidationError
from ..models import SourceDefinition

_CATALOG_PACKAGE = "rhinestone.catalogs"


def load_catalog_resource(name: str) -> Any:
    """Load one JSON resource from the repository-managed catalog."""
    if (
        not isinstance(name, str)
        or not name
        or "/" in name
        or "\\" in name
        or name in {".", ".."}
    ):
        raise ConfigValidationError("Catalog resource name must be a file name")
    try:
        text = resources.files(_CATALOG_PACKAGE).joinpath(name).read_text(
            encoding="utf-8"
        )
    except FileNotFoundError:
        raise ConfigValidationError(
            f"Catalog resource {name!r} was not found"
        ) from None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ConfigValidationError(
            f"Catalog resource {name!r} is invalid JSON"
        ) from None


def load_source_definitions(
    name: str = "sources.json",
) -> Tuple[SourceDefinition, ...]:
    """Load and validate the built-in Source definitions in catalog order."""
    document = load_catalog_resource(name)
    if not isinstance(document, Mapping):
        raise ConfigValidationError("Source catalog must be an object")
    raw_sources = document.get("sources")
    if not isinstance(raw_sources, Mapping) or not raw_sources:
        raise ConfigValidationError("Source catalog must define sources")

    definitions: List[SourceDefinition] = []
    for raw_id, raw_definition in raw_sources.items():
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ConfigValidationError("Source catalog ids must be non-empty strings")
        if not isinstance(raw_definition, Mapping):
            raise ConfigValidationError(
                f"Source catalog entry {raw_id!r} must be an object"
            )
        definition = cast(Mapping[str, Any], raw_definition)
        adapter_type = definition.get("adapter_type")
        if not isinstance(adapter_type, str) or not adapter_type.strip():
            raise ConfigValidationError(
                f"Source catalog entry {raw_id!r} requires adapter_type"
            )
        settings_value = definition.get("settings", {})
        if not isinstance(settings_value, Mapping):
            raise ConfigValidationError(
                f"Source catalog entry {raw_id!r} settings must be an object"
            )
        settings = cast(Mapping[str, Any], settings_value)
        definitions.append(
            SourceDefinition(
                id=raw_id,
                adapter_type=adapter_type,
                settings=settings,
            )
        )
    return tuple(definitions)


__all__ = ["load_catalog_resource", "load_source_definitions"]
