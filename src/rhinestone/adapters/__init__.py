"""Public Adapter exports loaded only when explicitly imported."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .contracts import (
        CredentialPort,
        DependencyPort,
        ProviderAdapterContext,
        ProviderAdapterDefinition,
        RuntimeAdapterContext,
        RuntimeAdapterDefinition,
        TransportPort,
    )
    from .knowledge import (
        KnowledgeAdapterContext,
        KnowledgeAdapterDefinition,
        KnowledgeAdapterRegistry,
        KnowledgePort,
    )
    from .provider import (
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
    from .runtime import RuntimeAdapter

_EXPORTS = {
    "CkanAdapter": ".provider",
    "DirectAdapter": ".provider",
    "EstatGisAdapter": ".provider",
    "DcatAdapter": ".provider",
    "GeospatialJpAdapter": ".provider",
    "GsiFundamentalAdapter": ".provider",
    "JsonGetter": ".provider",
    "JsonObject": ".provider",
    "OdptAdapter": ".provider",
    "OgcFeaturesAdapter": ".provider",
    "PlateauAdapter": ".provider",
    "ProviderAdapter": ".provider",
    "StacAdapter": ".provider",
    "StaticAdapter": ".provider",
    "RuntimeAdapter": ".runtime",
    "CredentialPort": ".contracts",
    "DependencyPort": ".contracts",
    "RuntimeAdapterContext": ".contracts",
    "RuntimeAdapterDefinition": ".contracts",
    "KnowledgeAdapterDefinition": ".knowledge",
    "KnowledgeAdapterContext": ".knowledge",
    "KnowledgeAdapterRegistry": ".knowledge",
    "KnowledgePort": ".knowledge",
    "ProviderAdapterContext": ".contracts",
    "ProviderAdapterDefinition": ".contracts",
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
    "RuntimeAdapter",
    "CredentialPort",
    "DependencyPort",
    "RuntimeAdapterContext",
    "RuntimeAdapterDefinition",
    "KnowledgeAdapterDefinition",
    "KnowledgeAdapterContext",
    "KnowledgeAdapterRegistry",
    "KnowledgePort",
    "ProviderAdapterContext",
    "ProviderAdapterDefinition",
    "TransportPort",
]
