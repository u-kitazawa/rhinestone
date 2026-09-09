"""Built-in source adapters."""

from .base import JsonGetter, JsonObject, ProviderAdapter
from .ckan import CkanAdapter
from .dcat import DcatAdapter
from .direct import DirectAdapter
from .gsi_fundamental import GsiFundamentalAdapter
from .odpt import OdptAdapter
from .ogc import OgcFeaturesAdapter
from .plateau import PlateauAdapter
from .search_ckan_jp import SearchCkanJpAdapter
from .stac import StacAdapter
from .static import StaticAdapter

__all__ = [
    "CkanAdapter",
    "DirectAdapter",
    "DcatAdapter",
    "GsiFundamentalAdapter",
    "JsonGetter",
    "JsonObject",
    "OdptAdapter",
    "OgcFeaturesAdapter",
    "PlateauAdapter",
    "ProviderAdapter",
    "StacAdapter",
    "StaticAdapter",
    "SearchCkanJpAdapter",
]
