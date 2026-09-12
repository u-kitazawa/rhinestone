"""Small public contracts used to compose user-owned adapters."""

from dataclasses import dataclass, field
from typing import Any, Callable, FrozenSet, Protocol, Tuple

from ..models import Config, Provider, Resource, Result, Source
from ..registry import CredentialRegistry, DependencyRegistry
from ..security import DestinationPolicy


class SourceAdapter(Protocol):
    def load(self, config: Config) -> Source: ...


class SearchableSourceAdapter(SourceAdapter, Protocol):
    def search(self, query: Any) -> Tuple[Result, ...]: ...


class ExecutionAdapter(Protocol):
    name: str
    priority: int

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool: ...

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class SourceAdapterContext:
    """Framework services available to a Source Adapter factory."""

    get_json: Callable[..., Any]
    get_text: Callable[[str], str]
    credentials: CredentialRegistry
    dependencies: DependencyRegistry
    destination_policy: DestinationPolicy
    provider_id: str


@dataclass(frozen=True)
class ExecutionAdapterContext:
    """Framework services available to an Execution Adapter factory."""

    credentials: CredentialRegistry
    dependencies: DependencyRegistry
    destination_policy: DestinationPolicy


SourceAdapterFactory = Callable[[Provider, SourceAdapterContext], SourceAdapter]
ExecutionAdapterFactory = Callable[[ExecutionAdapterContext], ExecutionAdapter]


@dataclass(frozen=True)
class SourceAdapterDefinition:
    """Register one reusable provider-specific Source Adapter factory."""

    adapter_type: str
    factory: SourceAdapterFactory
    dependencies: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.adapter_type.strip():
            raise ValueError("adapter_type must be a non-empty string")
        if not callable(self.factory):
            raise ValueError("factory must be callable")
        object.__setattr__(self, "dependencies", frozenset(self.dependencies))


@dataclass(frozen=True)
class ExecutionAdapterDefinition:
    """Register one user-owned Execution Adapter factory."""

    name: str
    factory: ExecutionAdapterFactory

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not callable(self.factory):
            raise ValueError("factory must be callable")


AdapterDefinition = SourceAdapterDefinition | ExecutionAdapterDefinition


__all__ = [
    "AdapterDefinition",
    "ExecutionAdapter",
    "ExecutionAdapterContext",
    "ExecutionAdapterDefinition",
    "SearchableSourceAdapter",
    "SourceAdapter",
    "SourceAdapterContext",
    "SourceAdapterDefinition",
]
