"""Public Adapter exports loaded only when explicitly imported."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .area import StaticAdministrativeAreaAdapter
    from .base import (
        AreaKnowledgeAdapter,
        IdentityKnowledgeAdapter,
        KnowledgeAdapter,
        KnowledgeAdapterContext,
        KnowledgeAdapterDefinition,
        KnowledgeAdapterFactory,
        KnowledgeKind,
        KnowledgePort,
        TimeKnowledgeAdapter,
    )
    from .models import AdministrativeArea, MunicipalityIdentity, TimeKind, TimeSemantic
    from .municipality import (
        STANDARD_AREA_CODE,
        AreaCode,
        MunicipalityRecord,
        StaticMunicipalityAdapter,
    )
    from .registry import KnowledgeAdapterRegistry
    from .space import (
        CRS84,
        BoundingBox,
        CRSRef,
        MeshCode,
        MeshLevel,
        require_lossless_crs84,
    )
    from .time import StandardTimeAdapter

_EXPORTS = {
    "AdministrativeArea": ".models",
    "AreaKnowledgeAdapter": ".base",
    "IdentityKnowledgeAdapter": ".base",
    "KnowledgeAdapter": ".base",
    "KnowledgeAdapterContext": ".base",
    "KnowledgeAdapterDefinition": ".base",
    "KnowledgeAdapterFactory": ".base",
    "KnowledgeAdapterRegistry": ".registry",
    "KnowledgeKind": ".base",
    "KnowledgePort": ".base",
    "AreaCode": ".municipality",
    "BoundingBox": ".space",
    "CRS84": ".space",
    "CRSRef": ".space",
    "MeshCode": ".space",
    "MeshLevel": ".space",
    "MunicipalityIdentity": ".models",
    "MunicipalityRecord": ".municipality",
    "STANDARD_AREA_CODE": ".municipality",
    "StandardTimeAdapter": ".time",
    "StaticAdministrativeAreaAdapter": ".area",
    "StaticMunicipalityAdapter": ".municipality",
    "TimeKind": ".models",
    "TimeKnowledgeAdapter": ".base",
    "TimeSemantic": ".models",
    "require_lossless_crs84": ".space",
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
    "AdministrativeArea",
    "AreaKnowledgeAdapter",
    "IdentityKnowledgeAdapter",
    "KnowledgeAdapter",
    "KnowledgeAdapterContext",
    "KnowledgeAdapterDefinition",
    "KnowledgeAdapterFactory",
    "KnowledgeAdapterRegistry",
    "KnowledgeKind",
    "KnowledgePort",
    "AreaCode",
    "BoundingBox",
    "CRS84",
    "CRSRef",
    "MeshCode",
    "MeshLevel",
    "MunicipalityIdentity",
    "MunicipalityRecord",
    "STANDARD_AREA_CODE",
    "StandardTimeAdapter",
    "StaticAdministrativeAreaAdapter",
    "StaticMunicipalityAdapter",
    "TimeKind",
    "TimeKnowledgeAdapter",
    "TimeSemantic",
    "require_lossless_crs84",
]
