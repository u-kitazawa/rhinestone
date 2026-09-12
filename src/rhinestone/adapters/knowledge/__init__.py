"""Shared knowledge adapters."""

from .base import (
    IdentityKnowledgeAdapter,
    KnowledgeAdapter,
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterFactory,
    KnowledgeKind,
    TimeKnowledgeAdapter,
)
from .models import MunicipalityIdentity, TimeKind, TimeSemantic
from .registry import KnowledgeAdapterRegistry
from .time import StandardTimeAdapter

__all__ = [
    "IdentityKnowledgeAdapter",
    "KnowledgeAdapter",
    "KnowledgeAdapterContext",
    "KnowledgeAdapterDefinition",
    "KnowledgeAdapterFactory",
    "KnowledgeAdapterRegistry",
    "KnowledgeKind",
    "MunicipalityIdentity",
    "StandardTimeAdapter",
    "TimeKind",
    "TimeKnowledgeAdapter",
    "TimeSemantic",
]
