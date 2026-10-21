"""Public Adapter exports loaded only when explicitly imported."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import JsonGetter, JsonObject, ProviderAdapter
    from .ckan import CkanAdapter
    from .dcat import DcatAdapter
    from .direct import DirectAdapter
    from .estat_gis import EstatGisAdapter
    from .geospatial_jp import GeospatialJpAdapter
    from .gsi_fundamental import GsiFundamentalAdapter
    from .mlit_dpf import MlitDpfAdapter
    from .odpt import OdptAdapter
    from .ogc import OgcFeaturesAdapter
    from .plateau import PlateauAdapter
    from .search_ckan_jp import SearchCkanJpAdapter
    from .stac import StacAdapter
    from .static import StaticAdapter

_EXPORTS = {
    "CkanAdapter": ".ckan",
    "DirectAdapter": ".direct",
    "EstatGisAdapter": ".estat_gis",
    "DcatAdapter": ".dcat",
    "GeospatialJpAdapter": ".geospatial_jp",
    "GsiFundamentalAdapter": ".gsi_fundamental",
    "JsonGetter": ".base",
    "JsonObject": ".base",
    "MlitDpfAdapter": ".mlit_dpf",
    "OdptAdapter": ".odpt",
    "OgcFeaturesAdapter": ".ogc",
    "PlateauAdapter": ".plateau",
    "ProviderAdapter": ".base",
    "StacAdapter": ".stac",
    "StaticAdapter": ".static",
    "SearchCkanJpAdapter": ".search_ckan_jp",
}


def __getattr__(name: str) -> Any:
    try:
        module = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


__all__ = [
    "CkanAdapter",
    "DirectAdapter",
    "EstatGisAdapter",
    "DcatAdapter",
    "GeospatialJpAdapter",
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
