"""Shared knowledge adapters."""

from .base import (
    IdentityKnowledgeAdapter,
    KnowledgeAdapter,
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterFactory,
    KnowledgeKind,
    KnowledgePort,
    TimeKnowledgeAdapter,
)
from .models import MunicipalityIdentity, TimeKind, TimeSemantic
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

__all__ = [
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
    "StaticMunicipalityAdapter",
    "TimeKind",
    "TimeKnowledgeAdapter",
    "TimeSemantic",
    "require_lossless_crs84",
]
