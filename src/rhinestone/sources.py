"""Compatibility facade for the built-in Provider catalog."""

from typing import Dict, List, Tuple

from .catalogs import Catalog, CatalogSource, load_source_catalog
from .models import Provider

_CATALOG: Tuple[CatalogSource, ...] = load_source_catalog()
_BUILTINS: Dict[str, Provider] = {
    entry.definition.id: entry.definition for entry in _CATALOG
}
_BY_NAME: Dict[str, Provider] = {entry.name: entry.definition for entry in _CATALOG}

CATALOG = Catalog(tuple(entry.definition for entry in _CATALOG))
ALL: Tuple[Provider, ...] = CATALOG.providers


def __getattr__(name: str) -> Provider:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise AttributeError(
            f"module {__name__!r} has no source named {name!r}"
        ) from None


def __dir__() -> List[str]:
    return sorted(set(globals()) | set(_BY_NAME))


__all__ = ["ALL", *sorted(_BY_NAME)]  # pyright: ignore[reportUnsupportedDunderAll]
