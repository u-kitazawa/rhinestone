"""Public composition API."""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from typing import Protocol, cast, runtime_checkable

from . import _http
from ._composition import (
    ConfiguredProviderAdapter,
    build_provider_adapter,
    provider_context,
    split_definitions,
    validate_mlit_dpf_targets,
)
from ._composition import (
    knowledge_definitions as compose_knowledge_definitions,
)
from ._composition import (
    provider_definitions as compose_provider_definitions,
)
from ._composition import (
    runtime_definitions as compose_runtime_definitions,
)
from ._entry_points import (
    KNOWLEDGE_GROUP,
    PROVIDER_GROUP,
    RUNTIME_GROUP,
    DefinitionIndex,
    discover,
)
from ._knowledge_adapters import select_knowledge
from ._runtime_adapters import RuntimeInstances
from .adapters.contracts import (
    AdapterDefinition,
    ProviderAdapterDefinition,
    RuntimeAdapter,
    RuntimeAdapterContext,
    RuntimeAdapterDefinition,
)
from .adapters.knowledge import (
    KnowledgeAdapterContext,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterRegistry,
    KnowledgeKind,
)
from .catalogs import Catalog
from .errors import (
    AdapterContractError,
    AdapterFactoryError,
    AdapterRegistrationError,
    ConfigValidationError,
    RuntimeAdapterUnavailableError,
)
from .models import (
    AccessPlan,
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
from .runtime import RuntimeAdapterSelector
from .search import SearchCoordinator, SearchResults
from .security import DestinationPolicy, NetworkPolicyLevel


@runtime_checkable
class _CredentialBindableRuntimeAdapter(Protocol):
    """Optional capability for adapters using application credentials."""

    def bind_credentials(self, credentials: CredentialRegistry) -> RuntimeAdapter:
        """Return an adapter bound to the application credential registry."""
        ...


class Rhinestone:
    """An isolated application context for discovery, planning, and access.

    Each instance owns its configured Providers, Provider dependencies, credential
    factories, network policy, and adapter registry. It is safe to create
    separate instances with different credentials or runtime objects in the
    same process.

    Use :func:`configure` for the usual construction path. The public workflow
    is ``search -> open``; known Provider selections can start with
    ``load(Reference(...))`` instead. Use ``plan(resource)`` for transfer.
    """

    def __init__(
        self,
        *,
        catalog: Catalog | None = None,
        dependencies: Mapping[str, DependencyValue] | None = None,
        credentials: Mapping[str, Callable[[], str]] | None = None,
        network_policy: NetworkPolicyLevel = "credentialed",
        adapters: Iterable[AdapterDefinition] = (),
        knowledge: Mapping[KnowledgeKind, str] | None = None,
    ) -> None:
        selected_sources = tuple(catalog) if catalog is not None else ()

        validate_mlit_dpf_targets(selected_sources)

        (
            customprovider_definitions,
            customruntime_definitions,
            customknowledge_definitions,
        ) = split_definitions(adapters)
        discovered = discover()
        provider_definitions = DefinitionIndex(
            compose_provider_definitions(customprovider_definitions),
            discovered[PROVIDER_GROUP],
            ProviderAdapterDefinition,
            lambda definition: definition.adapter_type,
        )
        runtime_definitions = DefinitionIndex(
            {
                definition.name: definition
                for definition in compose_runtime_definitions(customruntime_definitions)
            },
            discovered[RUNTIME_GROUP],
            RuntimeAdapterDefinition,
            lambda definition: definition.name,
        )
        knowledge_definitions = DefinitionIndex(
            compose_knowledge_definitions(customknowledge_definitions),
            discovered[KNOWLEDGE_GROUP],
            KnowledgeAdapterDefinition,
            lambda definition: definition.adapter_type,
        )
        selected_knowledge = select_knowledge(knowledge_definitions, knowledge)
        runtime_dependencies = dict(dependencies or {})
        runtime_adapter_names = frozenset(runtime_definitions)
        invalid_dependencies = runtime_adapter_names.intersection(runtime_dependencies)
        if invalid_dependencies:
            raise ConfigValidationError(
                "Runtime names are not valid configure dependencies: "
                + ", ".join(sorted(invalid_dependencies))
            )
        source_dependency_registry = DependencyRegistry(runtime_dependencies)
        credential_registry = CredentialRegistry(credentials or {})
        destination_policy = DestinationPolicy.from_catalog(
            selected_sources, level=network_policy
        )
        knowledge_registry = KnowledgeAdapterRegistry(
            selected_knowledge,
            KnowledgeAdapterContext(
                get_json=_http.get_json,
                get_text=_http.get_text,
                credentials=credential_registry,
                dependencies=source_dependency_registry,
                destination_policy=destination_policy,
            ),
            origins={
                definition.kind: origin
                for definition in selected_knowledge
                if (origin := knowledge_definitions.origin(definition.adapter_type))
                is not None
            },
        )

        configured_sources: list[ConfiguredProviderAdapter] = []
        configured_ids = {"direct"}
        direct_provider = Provider("direct", "direct")
        configured_sources.append(
            ConfiguredProviderAdapter(
                "direct",
                build_provider_adapter(
                    direct_provider,
                    provider_definitions,
                    provider_context(
                        direct_provider,
                        provider_definitions,
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
                ConfiguredProviderAdapter(
                    source_id,
                    build_provider_adapter(
                        source_definition,
                        provider_definitions,
                        provider_context(
                            source_definition,
                            provider_definitions,
                            source_dependency_registry,
                            knowledge_registry,
                            credential_registry,
                            destination_policy,
                        ),
                    ),
                    source_definition.adapter_type,
                )
            )

        provider_adapters = tuple(configured_sources)

        def bind_credentials(adapter: RuntimeAdapter) -> RuntimeAdapter:
            if isinstance(adapter, _CredentialBindableRuntimeAdapter):
                return adapter.bind_credentials(credential_registry)
            return adapter

        def build_runtime(definition: RuntimeAdapterDefinition) -> RuntimeAdapter:
            origin = runtime_definitions.origin(definition.name)
            try:
                execution = definition.factory(
                    RuntimeAdapterContext(
                        credentials=credential_registry,
                        destination_policy=destination_policy,
                    )
                )
                execution = bind_credentials(execution)
            except Exception:
                if origin is None:
                    raise
                raise AdapterFactoryError(
                    f"Installed adapter factory failed: {origin}; inspect its factory"
                ) from None
            name = getattr(execution, "name", None)
            if name != definition.name:
                raise AdapterContractError(
                    "Runtime adapter factory returned an inconsistent name; "
                    f"expected {definition.name!r}; return an adapter whose name "
                    f"matches its RuntimeAdapterDefinition ({origin or definition.name})"
                )
            if (
                type(getattr(execution, "priority", None)) is not int
                or not callable(getattr(execution, "supports", None))
                or not callable(getattr(execution, "open", None))
            ):
                raise AdapterContractError(
                    f"Runtime adapter must implement priority, supports, and open: "
                    f"{origin or definition.name}"
                )
            return execution

        # Preserve explicit application factory timing. Built-in and installed
        # Runtime implementations are needed only by a library selection.
        configured_runtimes = {
            definition.name: build_runtime(definition)
            for definition in customruntime_definitions
        }
        adapter_registry = AdapterRegistry(
            provider_adapters,
            RuntimeInstances(runtime_definitions, build_runtime, configured_runtimes),
        )
        self._pipeline = AccessPipeline(
            adapter_registry=adapter_registry,
            runtime_selector=RuntimeAdapterSelector(adapter_registry.runtime_adapters),
            destination_policy=destination_policy,
        )
        self._search = SearchCoordinator(provider_adapters, knowledge_registry)

    def load(self, value: Reference | Resource) -> Resource:
        """Load one concrete Resource from a Reference or deferred Resource.

        Raises:
            ConfigValidationError: If value is not a Reference or Resource.
            UnsupportedProviderError: If a Reference names an unconfigured Provider.
            ProviderMetadataError: If provider metadata cannot be loaded.
            UnsupportedAccessError: If the Provider cannot produce a unique
                portable access plan.
        """
        if not issubclass(type(cast(object, value)), Reference | Resource):
            raise ConfigValidationError("load value must be a Reference or Resource")
        if isinstance(value, Resource):
            if value.access_plan is not None:
                return self.bind(value)
            resource = self._pipeline.load(value.reference)
            return replace(resource, discovery=value.discovery or resource.discovery)
        return self._pipeline.load(value)

    def plan(self, value: Resource) -> AccessPlan:
        """Return a portable execution plan, loading a deferred Reference if needed."""
        resource = self.load(value)
        if resource.access_plan is None:
            raise RuntimeAdapterUnavailableError(
                "Resource has no AccessPlan; the Provider must declare its format "
                "or access kind"
            )
        return resource.access_plan

    def bind(self, value: Resource) -> Resource:
        """Bind a detached portable Resource to this execution context.

        Raises:
            ConfigValidationError: If value is not a Resource.
        """
        if not issubclass(type(cast(object, value)), Resource):
            raise ConfigValidationError("bind value must be a Resource")
        return self._pipeline.bind(value)

    def open(
        self,
        value: Reference | Resource | AccessPlan,
        library: LibraryName,
        *,
        runtime: object | None = None,
    ) -> object:
        """Resolve and open a value through an explicitly named runtime.

        Args:
            value: A ``Resource``, direct ``Reference``, or a
                standalone ``AccessPlan``.
            library: Runtime adapter name such as ``"rasterio"`` or
                ``"pyogrio"``.
            runtime: User-owned runtime object for external adapters.

        Raises:
            ConfigValidationError: If value is not a Reference, Resource, or
                AccessPlan, or library is not a non-empty adapter name.
            RuntimeAdapterUnavailableError: If the named adapter or injected
                runtime is unavailable or incompatible.
            ResourceAccessError: If the runtime cannot access the resource.
            DestinationNotAllowedError: If network policy rejects the URI.
        """
        if not issubclass(type(cast(object, value)), Reference | Resource | AccessPlan):
            raise ConfigValidationError(
                "open value must be a Reference, Resource, or AccessPlan"
            )
        raw_library = cast(object, library)
        if not isinstance(raw_library, str) or not raw_library.strip():
            raise ConfigValidationError(
                "library must be a non-empty runtime adapter name"
            )
        if isinstance(value, AccessPlan):
            return self._pipeline.open_plan(value, library, runtime=runtime)
        if isinstance(value, Resource):
            return self._pipeline.open_resource(
                self.load(value), library, runtime=runtime
            )
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
        else:
            query_type = type(cast(object, query))
            if issubclass(query_type, str):
                normalized_query = SearchQuery(text=cast(str, query))
            elif issubclass(query_type, SearchQuery):
                normalized_query = cast(SearchQuery, query)
            else:
                raise ConfigValidationError(
                    "query must be a SearchQuery, string, or None"
                )
        return self._search.search(normalized_query).bind(self.bind)


def configure(
    *,
    catalog: Catalog | None = None,
    dependencies: Mapping[str, DependencyValue] | None = None,
    credentials: Mapping[str, Callable[[], str]] | None = None,
    network_policy: NetworkPolicyLevel = "credentialed",
    adapters: Iterable[AdapterDefinition] = (),
    knowledge: Mapping[KnowledgeKind, str] | None = None,
) -> Rhinestone:
    """Create an isolated Rhinestone application.

    Args:
        catalog: Immutable Provider collection to enable.
        dependencies: User-owned Provider dependency objects or ``RuntimeFactory``
            values, keyed by runtime name. Runtime names are rejected.
        credentials: Lazy factories keyed by logical credential name. Secrets
            are not retained in public models.
        network_policy: ``"credentialed"`` (default) authorizes requests from
            catalog destinations; ``"none"`` disables destination restrictions.
        adapters: Additional Source, Execution, or Knowledge Adapter
            definitions. Installed Provider and Runtime Entry Points are also
            discovered; built-in and external Runtime adapters load only when selected by
            the explicit library name passed to open().
        knowledge: Explicit adapter identity for each shared knowledge kind.
            Unspecified area/time kinds use built-in defaults. Installing or
            registering an adapter never replaces a default by itself.

    Returns:
        A configured application whose ``search``, ``load``, ``plan``, and ``open``
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
        knowledge=knowledge,
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
