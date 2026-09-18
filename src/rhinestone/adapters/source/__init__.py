"""Built-in source adapters."""

from .base import JsonGetter, JsonObject, ProviderAdapter
from .ckan import CkanAdapter
from .dcat import DcatAdapter
from .direct import DirectAdapter
from .estat_gis import EstatGisAdapter
from .gsi_fundamental import GsiFundamentalAdapter
from .mlit_dpf import MlitDpfAdapter
from .odpt import OdptAdapter
from .ogc import OgcFeaturesAdapter
from .plateau import PlateauAdapter
from .search_ckan_jp import SearchCkanJpAdapter
from .stac import StacAdapter
from .static import StaticAdapter

__all__ = [
    "CkanAdapter",
    "DirectAdapter",
    "EstatGisAdapter",
    "DcatAdapter",
    "GsiFundamentalAdapter",
    "JsonGetter",
    "JsonObject",
    "MlitDpfAdapter",
    "OdptAdapter",
    "OgcFeaturesAdapter",
    "PlateauAdapter",
    "ProviderAdapter",
    "StacAdapter",
    "StaticAdapter",
    "SearchCkanJpAdapter",
]
