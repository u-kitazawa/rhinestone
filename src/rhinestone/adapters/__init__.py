"""Compatibility exports for built-in source adapters."""

from .execution import ExecutionAdapter
from .source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    EStatAdapter,
    GsiFundamentalAdapter,
    JsonGetter,
    JsonObject,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    StacAdapter,
    StaticAdapter,
)

__all__ = [
    "CkanAdapter",
    "DirectAdapter",
    "DcatAdapter",
    "EStatAdapter",
    "GsiFundamentalAdapter",
    "JsonGetter",
    "JsonObject",
    "OdptAdapter",
    "OgcFeaturesAdapter",
    "PlateauAdapter",
    "ProviderAdapter",
    "StacAdapter",
    "StaticAdapter",
    "ExecutionAdapter",
]
