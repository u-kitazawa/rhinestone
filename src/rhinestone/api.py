"""Public composition API."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from functools import lru_cache
from typing import Protocol, runtime_checkable

from . import _http
from ._composition import (
    ConfiguredSourceAdapter,
    build_source_adapter,
    source_context,
    split_definitions,
    validate_mlit_dpf_targets,
)
from ._composition import (
    execution_definitions as compose_execution_definitions,
)
from ._composition import (
    knowledge_definitions as compose_knowledge_definitions,
)
from ._composition import (
    source_definitions as compose_source_definitions,
)
from .adapters.contracts import (
    AdapterDefinition,
    ExecutionAdapter,
    ExecutionAdapterContext,
)
from .adapters.knowledge import (
    KnowledgeAdapterContext,
    KnowledgeAdapterRegistry,
)
from .catalogs import Catalog
from .errors import (
    AdapterRegistrationError,
    ConfigValidationError,
)
from .execution import ExecutionAdapterSelector
from .models import (
    AccessPlan,
    Config,
    DependencyValue,
    LibraryName,
    Provider,
    ProviderId,
    Reference,
    Resource,
    SearchQuery,
)
from .pipeline import AccessPipeline
from .registry import AdapterRegistry, CredentialRegistry, DependencyRegistry
from .representations import Format, FormatPreset
from .search import SearchCoordinator, SearchResults
from .security import DestinationPolicy, NetworkPolicyLevel


@runtime_checkable
class _CredentialBindableExecutionAdapter(Protocol):
    """Optional capability for adapters using application credentials."""

    def bind_credentials(self, credentials: CredentialRegistry) -> ExecutionAdapter:
        """Return an adapter bound to the application credential registry."""
        ...


class Rhinestone:
    """An isolated application context for discovery, resolution, and access.

    Each instance owns its configured Providers, Source runtimes, credential
    factories, network policy, and adapter registry. It is safe to create
    separate instances with different credentials or runtime objects in the
    same process.

    Use :func:`configure` for the usual construction path. The public workflow
    is ``search -> resolve -> open``; known Provider selections can start with
    ``resolve(Config(...))`` instead.
    """

    def __init__(
        self,
        *,
        catalog: Catalog | None = None,
        dependencies: Mapping[str, DependencyValue] | None = None,
        credentials: Mapping[str, Callable[[], str]] | None = None,
        network_policy: NetworkPolicyLevel = "credentialed",
        adapters: Iterable[AdapterDefinition] = (),
    ) -> None:
        selected_sources = tuple(catalog) if catalog is not None else ()

        validate_mlit_dpf_targets(selected_sources)

        (
            customsource_definitions,
            customexecution_definitions,
            customknowledge_definitions,
        ) = split_definitions(adapters)
        source_definitions = compose_source_definitions(customsource_definitions)
        execution_definitions = compose_execution_definitions(
            customexecution_definitions
        )
        knowledge_definitions = compose_knowledge_definitions(
            customknowledge_definitions
        )
        runtime_dependencies = dict(dependencies or {})
        execution_runtime_names = frozenset(
            definition.name for definition in execution_definitions
        )
        invalid_dependencies = execution_runtime_names.intersection(
            runtime_dependencies
        )
        if invalid_dependencies:
            raise ConfigValidationError(
                "Execution runtime names are not valid configure dependencies: "
                + ", ".join(sorted(invalid_dependencies))
            )
        source_dependency_registry = DependencyRegistry(runtime_dependencies)
        credential_registry = CredentialRegistry(credentials or {})
        destination_policy = DestinationPolicy.from_catalog(
            selected_sources, level=network_policy
        )
        knowledge_registry = KnowledgeAdapterRegistry(
            knowledge_definitions,
            KnowledgeAdapterContext(
                get_json=_http.get_json,
                get_text=_http.get_text,
                credentials=credential_registry,
                dependencies=source_dependency_registry,
                destination_policy=destination_policy,
            ),
        )

        configured_sources: list[ConfiguredSourceAdapter] = []
        configured_ids = {"direct"}
        direct_provider = Provider("direct", "direct")
        configured_sources.append(
            ConfiguredSourceAdapter(
                "direct",
                build_source_adapter(
                    direct_provider,
                    source_definitions,
                    source_context(
                        direct_provider,
                        source_definitions,
                        source_dependency_registry,
                        knowledge_registry,
                        credential_registry,
                        destination_policy,
                    ),
                ),
                "direct",
            )
        )
        for source_definition in selected_sources:
            source_id = source_definition.id
            if source_id in configured_ids:
                raise AdapterRegistrationError(
                    f"Source {source_id!r} is registered more than once; each "
                    "Provider.id must be unique"
                )
            configured_ids.add(source_id)
            configured_sources.append(
                ConfiguredSourceAdapter(
                    source_id,
                    build_source_adapter(
                        source_definition,
                        source_definitions,
                        source_context(
                            source_definition,
                            source_definitions,
                            source_dependency_registry,
                            knowledge_registry,
                            credential_registry,
                            destination_policy,
                        ),
                    ),
                    source_definition.adapter_type,
                )
            )

        source_adapters = tuple(configured_sources)

        def bind_credentials(adapter: ExecutionAdapter) -> ExecutionAdapter:
            if isinstance(adapter, _CredentialBindableExecutionAdapter):
                return adapter.bind_credentials(credential_registry)
            return adapter

        configured_executions: list[ExecutionAdapter] = []
        for definition in execution_definitions:
            execution = definition.factory(
                ExecutionAdapterContext(
                    credentials=credential_registry,
                    destination_policy=destination_policy,
                )
            )
            if execution.name != definition.name:
                raise AdapterRegistrationError(
                    f"Execution adapter factory returned {execution.name!r}; "
                    f"expected {definition.name!r}; return an adapter whose name "
                    "matches its ExecutionAdapterDefinition"
                )
            configured_executions.append(execution)
        adapter_registry = AdapterRegistry(
            source_adapters,
            (bind_credentials(adapter) for adapter in configured_executions),
        )
        self._pipeline = AccessPipeline(
            adapter_registry=adapter_registry,
            execution_selector=ExecutionAdapterSelector(
                adapter_registry.execution_adapters
            ),
            destination_policy=destination_policy,
        )
        self._search = SearchCoordinator(source_adapters, knowledge_registry)

    def resolve(self, value: Config | Reference | Resource) -> Resource:
        """Load one concrete Resource from a Config or Reference.

        Raises:
            UnsupportedSourceError: If a Config names an unconfigured source.
            ProviderMetadataError: If provider metadata cannot be loaded.
            UnsupportedAccessError: If the Provider cannot produce a unique
                portable access plan.
        """
        if isinstance(value, Resource):
            if value.access_plan is not None:
                return self.bind(value)
            return self._pipeline.resolve(value.reference)
        return self._pipeline.resolve(value)

    def bind(self, value: Resource) -> Resource:
        """Bind a detached portable Resource to this execution context."""
        return self._pipeline.bind(value)

    def open(
        self,
        value: Config | Reference | Resource | AccessPlan,
        library: LibraryName,
        *,
        runtime: object | None = None,
    ) -> object:
        """Resolve and open a value through an explicitly named runtime.

        Args:
            value: A ``Resource``, direct ``Reference``/``Config``, or a
                standalone ``AccessPlan``.
            library: Execution adapter name such as ``"rasterio"`` or
                ``"pyogrio"``.
            runtime: User-owned runtime object for external adapters.

        Raises:
            ExecutionAdapterUnavailableError: If the named adapter or injected
                runtime is unavailable or incompatible.
            ResourceAccessError: If the runtime cannot access the resource.
            DestinationNotAllowedError: If network policy rejects the URI.
        """
        if isinstance(value, AccessPlan):
            return self._pipeline.open_plan(value, library, runtime=runtime)
        if isinstance(value, Resource):
            return self._pipeline.open_resource(value, library, runtime=runtime)
        return self._pipeline.open(value, library=library, runtime=runtime)

    def search(
        self,
        query: SearchQuery | str | None = None,
        *,
        text: str | None = None,
        area: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        time: tuple[datetime | None, datetime | None] | None = None,
        format: tuple[Format | FormatPreset, ...] | None = None,
        limit: int | None = None,
        providers: Sequence[ProviderId | str] | None = None,
    ) -> SearchResults:
        """Search all configured searchable sources in configuration order.

        Args:
            query: A ``SearchQuery`` or shorthand text query.
            text: Free-text search condition.
            area: Administrative-area name, alias, or code.
            bbox: ``(west, south, east, north)`` geographic bounding box.
            time: ``(start, end)`` datetime interval; either endpoint may be
                ``None``.
            limit: Non-negative result limit passed to capable sources.
            providers: Provider IDs to search. None uses all configured Providers;
                an empty array searches none. Catalog order is preserved.

        Returns:
            ``SearchResults`` grouped by source and traversable in deterministic
            configuration order. Unsupported conditions and isolated provider
            failures are available in ``result.diagnostics``.

        Raises:
            ConfigValidationError: If a query value has an invalid shape or
                type.
            TypeError: If both ``query`` and shorthand search parameters are
                supplied.
        """
        supplied_parameters = (text, area, bbox, time, format, limit, providers)
        if query is not None and any(
            parameter is not None for parameter in supplied_parameters
        ):
            raise TypeError("pass either query or search parameters, not both")
        if query is None:
            normalized_query = SearchQuery(
                text=text,
                area=area,
                bbox=bbox,
                time=time,
                format=format,
                limit=limit,
                providers=providers,
            )
        elif isinstance(query, str):
            normalized_query = SearchQuery(text=query)
        else:
            normalized_query = query
        return self._search.search(normalized_query).bind(self.bind)


def configure(
    *,
    catalog: Catalog | None = None,
    dependencies: Mapping[str, DependencyValue] | None = None,
    credentials: Mapping[str, Callable[[], str]] | None = None,
    network_policy: NetworkPolicyLevel = "credentialed",
    adapters: Iterable[AdapterDefinition] = (),
) -> Rhinestone:
    """Create an isolated Rhinestone application.

    Args:
        catalog: Immutable Provider collection to enable.
        dependencies: User-owned Source runtime objects or ``RuntimeFactory``
            values, keyed by runtime name. Execution runtime names are rejected.
        credentials: Lazy factories keyed by logical credential name. Secrets
            are not retained in public models.
        network_policy: ``"credentialed"`` (default) authorizes requests from
            catalog destinations; ``"none"`` disables destination restrictions.
        adapters: Additional Source, Execution, or Knowledge Adapter
            definitions.

    Returns:
        A configured application whose ``search``, ``resolve``, and ``open``
        methods share the same registries and security policy.

    Raises:
        ConfigValidationError: If a source or policy setting is invalid.
        AdapterRegistrationError: If definitions conflict or a factory returns
            an inconsistent adapter.
    """
    return Rhinestone(
        catalog=catalog,
        dependencies=dependencies,
        credentials=credentials,
        network_policy=network_policy,
        adapters=adapters,
    )


@lru_cache(maxsize=1)
def _default_application() -> Rhinestone:
    """Build the immutable standard application on first use."""
    from .catalogs import BUILTIN

    return Rhinestone(catalog=BUILTIN)


def search(
    query: SearchQuery | str | None = None,
    *,
    text: str | None = None,
    area: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    time: tuple[datetime | None, datetime | None] | None = None,
    format: tuple[Format | FormatPreset, ...] | None = None,
    limit: int | None = None,
    providers: Sequence[ProviderId | str] | None = None,
) -> SearchResults:
    """Search the built-in catalog without explicit application setup.

    The standard application is created lazily and cannot be modified through
    :func:`configure`. Results retain that application context, so callers can
    open the returned Resource directly.
    """
    return _default_application().search(
        query,
        text=text,
        area=area,
        bbox=bbox,
        time=time,
        format=format,
        limit=limit,
        providers=providers,
    )
