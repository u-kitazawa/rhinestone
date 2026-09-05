"""Public composition API."""

from typing import Any, Callable, Iterable, Mapping, Optional, Tuple

from .execution import ExecutionAdapterSelector
from .models import Config, Resource, SearchQuery
from .pipeline import AccessPipeline
from .registry import CredentialRegistry, DependencyRegistry
from .resolution import Resolver
from .search import SearchCoordinator


class Rhinestone:
    """An isolated configured Rhinestone application context."""

    def __init__(
        self,
        dependencies: Mapping[str, Callable[[], Any]],
        source_adapters: Iterable[Any],
        execution_adapters: Iterable[Any],
        credentials: Optional[Mapping[str, Callable[[], str]]] = None,
    ) -> None:
        credential_registry = CredentialRegistry(credentials or {})

        def bind(adapter: Any) -> Any:
            binder = getattr(adapter, "bind_credentials", None)
            return binder(credential_registry) if callable(binder) else adapter

        sources = tuple(bind(adapter) for adapter in source_adapters)
        dependency_registry = DependencyRegistry(dependencies)
        self._pipeline = AccessPipeline(
            source_adapters=sources,
            resolver=Resolver(),
            execution_selector=ExecutionAdapterSelector(
                bind(adapter) for adapter in execution_adapters
            ),
            dependencies=dependency_registry,
        )
        self._search = SearchCoordinator(sources)

    def resolve(self, config: Config) -> Resource:
        return self._pipeline.resolve(config)

    def open(self, config: Config, adapter: Optional[str] = None) -> Any:
        return self._pipeline.open(config, adapter=adapter)

    def search(self, query: SearchQuery) -> Mapping[str, Tuple[Any, ...]]:
        return self._search.search(query)


def configure(
    dependencies: Mapping[str, Callable[[], Any]],
    source_adapters: Iterable[Any],
    execution_adapters: Iterable[Any],
    credentials: Optional[Mapping[str, Callable[[], str]]] = None,
) -> Rhinestone:
    """Create an isolated application context without loading dependencies."""
    return Rhinestone(dependencies, source_adapters, execution_adapters, credentials)
