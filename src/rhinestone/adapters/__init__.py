"""Public Adapter exports loaded only when explicitly imported."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
        GeospatialJpAdapter,
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

_EXPORTS = {
    "CkanAdapter": ".source",
    "DirectAdapter": ".source",
    "EstatGisAdapter": ".source",
    "DcatAdapter": ".source",
    "GeospatialJpAdapter": ".source",
    "GsiFundamentalAdapter": ".source",
    "JsonGetter": ".source",
    "JsonObject": ".source",
    "OdptAdapter": ".source",
    "OgcFeaturesAdapter": ".source",
    "PlateauAdapter": ".source",
    "ProviderAdapter": ".source",
    "StacAdapter": ".source",
    "StaticAdapter": ".source",
    "ExecutionAdapter": ".execution",
    "CredentialPort": ".contracts",
    "DependencyPort": ".contracts",
    "ExecutionAdapterContext": ".contracts",
    "ExecutionAdapterDefinition": ".contracts",
    "KnowledgeAdapterDefinition": ".knowledge",
    "KnowledgeAdapterContext": ".knowledge",
    "KnowledgeAdapterRegistry": ".knowledge",
    "KnowledgePort": ".knowledge",
    "SourceAdapterContext": ".contracts",
    "SourceAdapterDefinition": ".contracts",
    "TransportPort": ".contracts",
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
