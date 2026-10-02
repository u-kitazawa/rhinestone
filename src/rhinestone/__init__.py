"""Rhinestone public package."""

from . import api as _api
from .api import Rhinestone, configure
from .catalogs import Catalog
from .models import Config, Provider, Resource, Result
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
    "SearchResults",
    "Resource",
    "Format",
    "FormatPreset",
]
