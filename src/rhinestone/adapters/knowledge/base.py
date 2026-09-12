"""Contracts for shared knowledge adapters."""

from dataclasses import dataclass
from typing import Any, Callable, FrozenSet, Literal, Protocol, Union

from ...registry import CredentialRegistry, DependencyRegistry
from ...security import DestinationPolicy
from .models import MunicipalityIdentity, TimeKind, TimeSemantic

KnowledgeKind = Literal["identity", "time"]


class IdentityKnowledgeAdapter(Protocol):
    """Resolve an explicit municipality name or code to canonical identity."""

    def resolve_municipality(self, value: str) -> MunicipalityIdentity: ...


class TimeKnowledgeAdapter(Protocol):
    """Resolve an explicit Japanese public-data time expression."""

    def resolve_time(
        self, value: str, *, kind: TimeKind | None = None
    ) -> TimeSemantic: ...


KnowledgeAdapter = Union[IdentityKnowledgeAdapter, TimeKnowledgeAdapter]


@dataclass(frozen=True)
class KnowledgeAdapterContext:
    """Framework services available to a Knowledge Adapter factory."""

    get_json: Callable[..., Any]
    get_text: Callable[[str], str]
    credentials: CredentialRegistry
    dependencies: DependencyRegistry
    destination_policy: DestinationPolicy


KnowledgeAdapterFactory = Callable[[KnowledgeAdapterContext], KnowledgeAdapter]


@dataclass(frozen=True)
class KnowledgeAdapterDefinition:
    """Register one reusable shared knowledge adapter factory."""

    adapter_type: str
    factory: KnowledgeAdapterFactory
    kind: KnowledgeKind
    dependencies: FrozenSet[str] = frozenset()

    def __post_init__(self) -> None:
        if self.kind not in {"identity", "time"}:
            raise ValueError("knowledge adapter kind must be 'identity' or 'time'")
        if not self.adapter_type.strip():
            raise ValueError("knowledge adapter type must be a non-empty string")
        if not callable(self.factory):
            raise ValueError("knowledge adapter factory must be callable")
        object.__setattr__(self, "dependencies", frozenset(self.dependencies))


__all__ = [
    "IdentityKnowledgeAdapter",
    "KnowledgeAdapter",
    "KnowledgeAdapterContext",
    "KnowledgeAdapterDefinition",
    "KnowledgeAdapterFactory",
    "KnowledgeKind",
    "TimeKnowledgeAdapter",
]
