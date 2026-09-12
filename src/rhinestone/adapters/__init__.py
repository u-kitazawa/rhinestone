"""Compatibility exports for built-in source adapters."""

from .contracts import (
    ExecutionAdapterContext,
    ExecutionAdapterDefinition,
    SourceAdapterContext,
    SourceAdapterDefinition,
)
from .execution import ExecutionAdapter
from .source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
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
    "ExecutionAdapterContext",
    "ExecutionAdapterDefinition",
    "SourceAdapterContext",
    "SourceAdapterDefinition",
]
