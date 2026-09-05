"""Compatibility exports for built-in source adapters."""

from .execution import ExecutionAdapter
from .source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    EStatAdapter,
    GsiFundamentalAdapter,
    GsiTileAdapter,
    JsonGetter,
    JsonObject,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    StacAdapter,
)

__all__ = [
    "CkanAdapter",
    "DirectAdapter",
    "DcatAdapter",
    "GsiFundamentalAdapter",
    "GsiTileAdapter",
    "OdptAdapter",
    "PlateauAdapter",
    "EStatAdapter",
    "ExecutionAdapter",
    "JsonGetter",
    "JsonObject",
    "OgcFeaturesAdapter",
    "ProviderAdapter",
    "StacAdapter",
]
