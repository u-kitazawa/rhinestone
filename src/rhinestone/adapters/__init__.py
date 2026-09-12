"""Public exports for built-in adapters."""

from .contracts import (
    CredentialPort,
    DependencyPort,
    ExecutionAdapterContext,
    ExecutionAdapterDefinition,
    SourceAdapterContext,
    SourceAdapterDefinition,
    TransportPort,
)
from .execution import ExecutionAdapter
from .knowledge import (
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterRegistry,
    KnowledgePort,
)
from .source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    EstatGisAdapter,
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
    "EstatGisAdapter",
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
    "CredentialPort",
    "DependencyPort",
    "ExecutionAdapterContext",
    "ExecutionAdapterDefinition",
    "KnowledgeAdapterDefinition",
    "KnowledgeAdapterContext",
    "KnowledgeAdapterRegistry",
    "KnowledgePort",
    "SourceAdapterContext",
    "SourceAdapterDefinition",
    "TransportPort",
]
