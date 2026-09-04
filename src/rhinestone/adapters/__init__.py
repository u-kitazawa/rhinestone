"""Public provider adapter API and built-in implementations."""

from .base import JsonGetter, JsonObject, ProviderAdapter
from .ckan import CkanAdapter
from .estat import EStatAdapter
from .ogc import OgcFeaturesAdapter
from .stac import StacAdapter

__all__ = [
    "CkanAdapter",
    "EStatAdapter",
    "JsonGetter",
    "JsonObject",
    "OgcFeaturesAdapter",
    "ProviderAdapter",
    "StacAdapter",
]
