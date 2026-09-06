"""Public facade for built-in Source definitions."""

from typing import Dict, List, Tuple

from .catalogs import CatalogSource, load_source_catalog
from .models import SourceDefinition

_CATALOG: Tuple[CatalogSource, ...] = load_source_catalog()
_BUILTINS: Dict[str, SourceDefinition] = {
    entry.definition.id: entry.definition for entry in _CATALOG
}
_BY_NAME: Dict[str, SourceDefinition] = {
    entry.name: entry.definition for entry in _CATALOG
}

ALL: Tuple[SourceDefinition, ...] = tuple(_BUILTINS.values())


def __getattr__(name: str) -> SourceDefinition:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise AttributeError(
            f"module {__name__!r} has no source named {name!r}"
        ) from None


def __dir__() -> List[str]:
    return sorted(set(globals()) | set(_BY_NAME))


__all__ = ["ALL", *sorted(_BY_NAME)]  # pyright: ignore[reportUnsupportedDunderAll]
