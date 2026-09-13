"""Small public contracts used to compose user-owned adapters."""

from dataclasses import dataclass, field
from typing import Any, Callable, FrozenSet, Protocol, Tuple

from ..models import Config, Provider, Resource, Result, Source
from ..security import DestinationPolicy
from .knowledge.base import KnowledgeAdapterDefinition, KnowledgePort
from .ports import CredentialPort, DependencyPort, TransportPort


class SourceAdapter(Protocol):
    """Minimal contract for an adapter that turns Config into Source."""

    def load(self, config: Config) -> Source:
        """Load and normalize provider metadata for ``config``."""
        ...


class SearchableSourceAdapter(SourceAdapter, Protocol):
    """Optional Source Adapter contract for provider-backed search."""

    def search(self, query: Any) -> Tuple[Result, ...]:
        """Return results for the already projected source query."""
        ...


class ExecutionAdapter(Protocol):
    """Translate an explicit AccessPlan into a user-owned runtime call."""

    name: str
    priority: int

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        """Return whether this adapter can open ``resource`` with dependencies."""
        ...

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Open ``resource`` through the supplied runtime object."""
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

    Execution adapters receive credential lookup, scoped runtime dependencies,
    and the destination policy. They select no Resource; selection belongs to
    the Resolver and execution selector.
    """

    credentials: CredentialPort
    dependencies: DependencyPort
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
    dependencies: FrozenSet[str] = field(default_factory=lambda: frozenset[str]())

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
