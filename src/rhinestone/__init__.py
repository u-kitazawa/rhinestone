"""Rhinestone public package."""

from . import api as _api
from . import sources
from .api import Rhinestone, configure
from .catalogs import Catalog
from .models import Config, Provider, Resource, Result, SearchResult
from .representations import Format, FormatPreset
from .search import SearchResults

search = _api.search

__all__ = [
    "configure",
    "search",
    "Rhinestone",
    "Catalog",
    "Provider",
    "Config",
    "Result",
    "SearchResult",
    "SearchResults",
    "Resource",
    "Format",
    "FormatPreset",
    "sources",
]
