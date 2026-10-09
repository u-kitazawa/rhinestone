"""Rhinestone public package."""

from . import api as _api
from .api import Rhinestone, configure
from .catalogs import Catalog
from .models import Config, Provider, ProviderId, Reference, Resource
from .representations import Format, FormatPreset
from .search import SearchResults

search = _api.search

__all__ = [
    "configure",
    "search",
    "Rhinestone",
    "Catalog",
    "Provider",
    "ProviderId",
    "Config",
    "Reference",
    "SearchResults",
    "Resource",
    "Format",
    "FormatPreset",
]
