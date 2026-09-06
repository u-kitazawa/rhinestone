"""Built-in source adapters."""

from .base import JsonGetter, JsonObject, ProviderAdapter
from .ckan import CkanAdapter
from .dcat import DcatAdapter
from .direct import DirectAdapter
from .estat import EStatAdapter
from .gsi_fundamental import GsiFundamentalAdapter
from .gsi_tile import GsiTileAdapter
from .odpt import OdptAdapter
from .ogc import OgcFeaturesAdapter
from .plateau import PlateauAdapter
from .stac import StacAdapter
from .static import StaticAdapter

__all__ = [
    "CkanAdapter",
    "DirectAdapter",
    "DcatAdapter",
    "EStatAdapter",
    "GsiFundamentalAdapter",
    "GsiTileAdapter",
    "JsonGetter",
    "JsonObject",
    "OdptAdapter",
    "OgcFeaturesAdapter",
    "PlateauAdapter",
    "ProviderAdapter",
    "StacAdapter",
    "StaticAdapter",
]
