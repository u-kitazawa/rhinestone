"""Explicit selection of shared-knowledge identities from discovered definitions."""

from collections.abc import Mapping
from typing import cast

from ._entry_points import DefinitionIndex
from .adapters.knowledge.base import KnowledgeAdapterDefinition, KnowledgeKind
from .errors import (
    AdapterContractError,
    ConfigValidationError,
    KnowledgeAdapterUnavailableError,
)


def select_knowledge(
    definitions: DefinitionIndex[KnowledgeAdapterDefinition],
    selection: Mapping[KnowledgeKind, str] | None,
) -> tuple[KnowledgeAdapterDefinition, ...]:
    """Keep built-in defaults; only explicitly selected identities replace them."""
    selected: dict[KnowledgeKind, str] = {
        "area": "japan-administrative-area",
        "time": "standard-time",
    }
    if selection is not None:
        if not isinstance(cast(object, selection), Mapping):
            raise ConfigValidationError(
                "knowledge must map knowledge kinds to adapter identities"
            )
        for kind, name in selection.items():
            if kind not in {"area", "identity", "time"}:
                raise ConfigValidationError(
                    "knowledge kind must be area, identity, or time"
                )
            if not isinstance(cast(object, name), str) or not name.strip():
                raise ConfigValidationError(
                    "knowledge adapter identity must be a non-empty string"
                )
            selected[kind] = name
    result: list[KnowledgeAdapterDefinition] = []
    for kind, name in selected.items():
        try:
            definition = definitions[name]
        except KeyError:
            raise KnowledgeAdapterUnavailableError(
                f"Knowledge adapter {name!r} selected for {kind!r} is not registered"
            ) from None
        if definition.kind != kind:
            raise AdapterContractError(
                f"Knowledge adapter selected for {kind!r} declares {definition.kind!r}: "
                f"{definitions.origin(name) or name}"
            )
        result.append(definition)
    return tuple(result)
