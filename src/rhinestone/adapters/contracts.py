"""Small public contracts used to compose user-owned adapters."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..models import (
    AccessPlan,
    Provider,
    ProviderSearchResults,
    Reference,
    Resource,
    SearchQuery,
)
from ..security import DestinationPolicy
from .knowledge.base import KnowledgeAdapterDefinition, KnowledgePort
from .ports import CredentialPort, DependencyPort, TransportPort


class SourceAdapter(Protocol):
    """Minimal contract for a Provider adapter that loads one Resource."""

    def load(self, reference: Reference) -> Resource:
        """Load the unique delivery identified by ``reference``."""
        ...


@runtime_checkable
class SearchableSourceAdapter(SourceAdapter, Protocol):
    """Optional Source Adapter contract for provider-backed search."""

    search_conditions: frozenset[str]

    def search(
        self, query: SearchQuery
    ) -> tuple[Resource, ...] | ProviderSearchResults:
        """Return delivery Resources and optional item diagnostics."""
        ...


class ExecutionAdapter(Protocol):
    """Translate an explicit AccessPlan into a user-owned runtime call."""

    name: str
    priority: int

    def supports(self, plan: AccessPlan) -> bool:
        """Return whether this adapter supports the selected plan."""
        ...

    def open(
        self,
        plan: AccessPlan,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Open ``plan`` through the supplied runtime object."""
        ...


@dataclass(frozen=True)
class SourceAdapterContext:
    """Framework services injected into a Source Adapter factory.

    The context supplies transport, scoped dependencies, credential lookup,
    network authorization, provider identity, and shared knowledge adapters.
    Adapter factories should retain only the services they need.
    """

    transport: TransportPort
    credentials: CredentialPort
    dependencies: DependencyPort
    destination_policy: DestinationPolicy
    provider_id: str
    knowledge: KnowledgePort


@dataclass(frozen=True)
class ExecutionAdapterContext:
    """Framework services injected into an Execution Adapter factory.

    Execution adapters receive credential lookup and the destination policy.
    They select no Resource; selection belongs to
    the Resolver and execution selector.
    """

    credentials: CredentialPort
    destination_policy: DestinationPolicy


SourceAdapterFactory = Callable[[Provider, SourceAdapterContext], SourceAdapter]
ExecutionAdapterFactory = Callable[[ExecutionAdapterContext], ExecutionAdapter]


@dataclass(frozen=True)
class SourceAdapterDefinition:
    """Register one reusable provider-specific Source Adapter factory.

    ``adapter_type`` must be unique within the application. ``dependencies``
    limits which injected runtime names are visible to the factory and its
    adapter.
    """

    adapter_type: str
    factory: SourceAdapterFactory
    dependencies: frozenset[str] = field(default_factory=lambda: frozenset[str]())

    def __post_init__(self) -> None:
        if not self.adapter_type.strip():
            raise ValueError("adapter_type must be a non-empty string")
        if not callable(self.factory):
            raise ValueError("factory must be callable")
        object.__setattr__(self, "dependencies", frozenset(self.dependencies))


@dataclass(frozen=True)
class ExecutionAdapterDefinition:
    """Register one user-owned Execution Adapter factory.

    The factory must return an adapter whose ``name`` exactly matches this
    definition's ``name``; names already provided by built-ins cannot be reused.
    """

    name: str
    factory: ExecutionAdapterFactory

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not callable(self.factory):
            raise ValueError("factory must be callable")


AdapterDefinition = (
    SourceAdapterDefinition | ExecutionAdapterDefinition | KnowledgeAdapterDefinition
)


__all__ = [
    "AdapterDefinition",
    "CredentialPort",
    "DependencyPort",
    "ExecutionAdapter",
    "ExecutionAdapterContext",
    "ExecutionAdapterDefinition",
    "ExecutionAdapterFactory",
    "SearchableSourceAdapter",
    "SourceAdapter",
    "SourceAdapterContext",
    "SourceAdapterDefinition",
    "SourceAdapterFactory",
    "TransportPort",
]
