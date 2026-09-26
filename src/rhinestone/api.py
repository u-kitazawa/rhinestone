"""Public composition API."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any, cast

from . import _http
from .adapters.contracts import (
    AdapterDefinition,
    ExecutionAdapterContext,
    ExecutionAdapterDefinition,
    SourceAdapterContext,
    SourceAdapterDefinition,
)
from .adapters.execution import (
    GdalAdapter,
    JsonServiceAdapter,
    PyogrioAdapter,
    RasterioAdapter,
)
from .adapters.knowledge import (
    KnowledgeAdapterContext,
    StaticAdministrativeAreaAdapter,
    KnowledgeAdapterDefinition,
    KnowledgeAdapterRegistry,
    StandardTimeAdapter,
)
from .adapters.knowledge._japan_administrative_areas import (
    JAPAN_ADMINISTRATIVE_AREAS,
)
from .adapters.ports import TransportPort
from .adapters.source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    EstatGisAdapter,
    GsiFundamentalAdapter,
    MlitDpfAdapter,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    SearchCkanJpAdapter,
    StacAdapter,
    StaticAdapter,
)
from .catalogs import Catalog
from .errors import (
    AdapterRegistrationError,
    ConfigValidationError,
    ProviderMetadataError,
)
from .execution import ExecutionAdapterSelector
from .models import (
    Config,
    DependencyValue,
    DiscoveryRecord,
    LibraryName,
    Provider,
    Resource,
    Result,
    RuntimeFactory,
    SearchQuery,
    Source,
)
from .pipeline import AccessPipeline
from .registry import AdapterRegistry, CredentialRegistry, DependencyRegistry
from .resolution import Resolver
from .search import SearchCoordinator, SearchResults
from .security import DestinationPolicy, NetworkPolicyLevel


class _ConfiguredSourceAdapter:
    """Bind one public source id to one built-in adapter instance."""

    def __init__(
        self,
        source_id: str,
        source_adapter: ProviderAdapter,
        adapter_type: str | None = None,
    ) -> None:
        self.source_id = source_id
        self.adapter_type = adapter_type or source_adapter.adapter_type
        self.searchable = callable(getattr(source_adapter, "search", None))
        empty_conditions: frozenset[str] = frozenset()
        self.search_conditions = cast(
            frozenset[str],
            getattr(source_adapter, "search_conditions", empty_conditions),
        )
        self.required_search_conditions = cast(
            frozenset[str],
            getattr(source_adapter, "required_search_conditions", empty_conditions),
        )
        default_area_text_fallback = self.adapter_type in {
            "ckan",
            "dcat",
            "plateau",
            "search-ckan-jp",
            "static",
        }
        self.area_text_fallback = bool(
            getattr(
                source_adapter,
                "area_text_fallback",
                default_area_text_fallback,
            )
        )
        self._source_adapter = source_adapter

    def load(self, config: Config) -> Source:
        source = self._source_adapter.load(Config(self.adapter_type, config.settings))
        return replace(
            source,
            provenance=replace(source.provenance, provider=self.source_id),
        )

    def search(self, query: SearchQuery) -> tuple[Result, ...]:
        search_method = getattr(self._source_adapter, "search")
        search_results = cast(
            Callable[[SearchQuery], tuple[Result, ...]], search_method
        )
        return tuple(
            replace(
                result,
                discovered_by=self.source_id,
                target=(
                    Config(self.source_id, result.target.settings)
                    if result.target.source_id == self.adapter_type
                    else result.target
                ),
                provenance=(
                    replace(result.provenance, provider=self.source_id)
                    if result.target.source_id == self.adapter_type
                    else result.provenance
                ),
            )
            for result in search_results(query)
        )


class _SourceTransport:
    """Bind the core HTTP transport to one configured provider boundary."""

    def __init__(
        self,
        destination_policy: DestinationPolicy,
        source_id: str,
        adapter_type: str,
        credential_name: str | None = None,
    ) -> None:
        self._destination_policy = destination_policy
        self._source_id = source_id
        self._adapter_type = adapter_type
        self._credential_name = credential_name

    def get_json(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
        *,
        credential: str | None = None,
    ) -> Any:
        credential_name = self._credential_name if credential is None else credential
        self._authorize(url, headers, credential_name)
        request_headers = headers
        if headers is not None and (credential_name is not None or headers):
            request_headers = _NoRedirectHeaders(headers)
        try:
            if request_headers is None:
                return _http.get_json(url, params)
            return _http.get_json(url, params, request_headers)
        except OSError as error:
            raise ProviderMetadataError(
                f"Provider metadata request failed for {url!r}"
            ) from error

    def get_text(
        self,
        url: str,
        headers: Mapping[str, str] | None = None,
        *,
        credential: str | None = None,
    ) -> str:
        credential_name = self._credential_name if credential is None else credential
        self._authorize(url, headers, credential_name)
        try:
            if headers is None:
                return _http.get_text(url)
            return _http.get_text(url, headers)
        except OSError as error:
            raise ProviderMetadataError(
                f"Provider metadata request failed for {url!r}"
            ) from error

    def post_json(
        self,
        url: str,
        body: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
        *,
        credential: str | None = None,
    ) -> Any:
        credential_name = self._credential_name if credential is None else credential
        self._authorize(url, headers, credential_name)
        request_headers = _NoRedirectHeaders(headers or {})
        try:
            return _http.post_json(url, body, request_headers)
        except OSError as error:
            raise ProviderMetadataError(
                f"Provider metadata request failed for {url!r}"
            ) from error

    def _authorize(
        self,
        url: str,
        headers: Mapping[str, str] | None,
        credential_name: str | None,
    ) -> None:
        self._destination_policy.authorize(
            url,
            credentialed=credential_name is not None or bool(headers),
            provider=self._source_id,
            service=self._adapter_type,
            credential=credential_name,
        )


class _NoRedirectHeaders(dict[str, str]):
    """Mark custom transport headers as unsafe to forward across redirects."""

    _rhinestone_no_redirects = True


def _source_transport(
    provider: Provider, destination_policy: DestinationPolicy
) -> _SourceTransport:
    configured_credential = provider.settings.get("credential")
    credential = (
        configured_credential if isinstance(configured_credential, str) else None
    )
    return _SourceTransport(
        destination_policy,
        source_id=provider.id,
        adapter_type=provider.adapter_type,
        credential_name=credential,
    )


class Rhinestone:
    """An isolated application context for discovery, resolution, and access.

    Each instance owns its configured Providers, injected runtimes, credential
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
        sources: Iterable[Provider] = (),
        catalog: Catalog | None = None,
        dependencies: Mapping[str, DependencyValue] | None = None,
        credentials: Mapping[str, Callable[[], str]] | None = None,
        network_policy: NetworkPolicyLevel = "credentialed",
        adapters: Iterable[AdapterDefinition] = (),
    ) -> None:
        selected_sources = tuple(sources)
        if catalog is not None:
            if selected_sources:
                raise TypeError("pass either catalog or sources, not both")
            selected_sources = tuple(catalog)

        _validate_mlit_dpf_targets(selected_sources)

        (
            custom_source_definitions,
            custom_execution_definitions,
            custom_knowledge_definitions,
        ) = _split_definitions(adapters)
        source_definitions = _source_definitions(custom_source_definitions)
        execution_definitions = _execution_definitions(custom_execution_definitions)
        knowledge_definitions = _knowledge_definitions(custom_knowledge_definitions)
        execution_runtime_names = frozenset(
            definition.name for definition in execution_definitions
        )
        runtime_dependencies = dict(dependencies or {})
        source_dependency_registry = DependencyRegistry(runtime_dependencies)
        execution_dependencies = {
            name: value
            for name, value in runtime_dependencies.items()
            if name in execution_runtime_names
        }
        execution_dependencies.setdefault(
            "json-service", RuntimeFactory(lambda: _http.JsonServiceRuntime())
        )
        execution_dependency_registry = DependencyRegistry(execution_dependencies)
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

        configured_sources: list[_ConfiguredSourceAdapter] = []
        configured_ids = {"direct"}
        direct_provider = Provider("direct", "direct")
        configured_sources.append(
            _ConfiguredSourceAdapter(
                "direct",
                _build_source_adapter(
                    direct_provider,
                    source_definitions,
                    _source_context(
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
                _ConfiguredSourceAdapter(
                    source_id,
                    _build_source_adapter(
                        source_definition,
                        source_definitions,
                        _source_context(
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

        source_adapters: tuple[Any, ...] = tuple(configured_sources)

        def bind_credentials(adapter: Any) -> Any:
            credential_binder = getattr(adapter, "bind_credentials", None)
            return (
                credential_binder(credential_registry)
                if callable(credential_binder)
                else adapter
            )

        configured_executions: list[Any] = []
        for definition in execution_definitions:
            execution = definition.factory(
                ExecutionAdapterContext(
                    credentials=credential_registry,
                    dependencies=execution_dependency_registry,
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
            resolver=Resolver(),
            execution_selector=ExecutionAdapterSelector(
                adapter_registry.execution_adapters
            ),
            dependencies=execution_dependency_registry,
            destination_policy=destination_policy,
        )
        self._search = SearchCoordinator(source_adapters, knowledge_registry)

    def resolve(self, value: Config | Result) -> Resource:
        """Resolve a Config or search Result into one concrete Resource.

        ``Result`` metadata and provenance are preserved when discovery and
        resolution use different source adapters. Resolution fails explicitly
        when no candidate, multiple candidates, or no supported access plan is
        available.

        Raises:
            UnsupportedSourceError: If a Config names an unconfigured source.
            ProviderMetadataError: If provider metadata cannot be loaded.
            ResourceNotFoundError: If no candidate matches the selection.
            AmbiguousResourceError: If multiple candidates match.
            UnsupportedAccessError: If the candidate has no supported access
                plan.
        """
        if not isinstance(value, Result):
            return self._pipeline.resolve(value)
        resource = self._pipeline.resolve(value.to_config())
        if value.discovered_by == value.target.source_id:
            return resource
        return replace(
            resource,
            discovery=DiscoveryRecord(
                source_id=value.discovered_by,
                metadata=value.metadata,
                provenance=value.provenance,
                raw_metadata=value.raw_metadata,
            ),
        )

    def open(self, value: Config | Result | Resource, library: LibraryName) -> object:
        """Resolve and open a value through an explicitly named runtime.

        Args:
            value: An already resolved ``Resource``, a search ``Result``, or a
                direct ``Config``.
            library: Execution adapter name such as ``"rasterio"`` or
                ``"pyogrio"``.

        Raises:
            ExecutionAdapterUnavailableError: If the named adapter or injected
                runtime is unavailable or incompatible.
            ResourceAccessError: If the runtime cannot access the resource.
            DestinationNotAllowedError: If network policy rejects the URI.
        """
        if isinstance(value, Resource):
            return self._pipeline.open_resource(value, library)
        if isinstance(value, Config):
            return self._pipeline.open(value, library=library)
        return self.resolve(value).open(library)

    def search(
        self,
        query: SearchQuery | str | None = None,
        *,
        text: str | None = None,
        area: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
        time: tuple[datetime | None, datetime | None] | None = None,
        limit: int | None = None,
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
        supplied_parameters = (text, area, bbox, time, limit)
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
                limit=limit,
            )
        elif isinstance(query, str):
            normalized_query = SearchQuery(text=query)
        else:
            normalized_query = query
        return self._search.search(normalized_query).bind_resolver(self.resolve)


def configure(
    *,
    sources: Iterable[Provider] = (),
    catalog: Catalog | None = None,
    dependencies: Mapping[str, DependencyValue] | None = None,
    credentials: Mapping[str, Callable[[], str]] | None = None,
    network_policy: NetworkPolicyLevel = "credentialed",
    adapters: Iterable[AdapterDefinition] = (),
) -> Rhinestone:
    """Create an isolated Rhinestone application.

    Args:
        sources: Provider definitions to enable when ``catalog`` is omitted.
        catalog: Immutable Provider collection; mutually exclusive with
            ``sources``.
        dependencies: User-owned runtime objects or ``RuntimeFactory`` values,
            keyed by runtime name. Factories are evaluated lazily.
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
        sources=sources,
        catalog=catalog,
        dependencies=dependencies,
        credentials=credentials,
        network_policy=network_policy,
        adapters=adapters,
    )


def _build_builtin_source_adapter(
    provider: Provider,
    dependencies: DependencyRegistry,
    credentials: CredentialRegistry,
    destination_policy: DestinationPolicy | None = None,
    knowledge: KnowledgeAdapterRegistry | None = None,
    transport: TransportPort | None = None,
) -> ProviderAdapter:
    adapter_type = provider.adapter_type
    settings = dict(provider.settings)
    knowledge = knowledge or KnowledgeAdapterRegistry()
    destination_policy = destination_policy or DestinationPolicy.unrestricted()
    transport = transport or _source_transport(provider, destination_policy)

    def json_transport(
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return transport.get_json(url, params, headers)

    if adapter_type == "ckan":
        _reject_options(
            adapter_type,
            settings,
            ("endpoint", "credential", "credential_header", "credential_scheme"),
        )
        return CkanAdapter(
            get_json=json_transport,
            credentials=credentials,
            destination_policy=destination_policy,
            provider_id=provider.id,
            **settings,
        )
    if adapter_type == "stac":
        _reject_options(
            adapter_type,
            settings,
            ("endpoint", "credential", "credential_header", "credential_scheme"),
        )
        return StacAdapter(
            get_json=json_transport,
            credentials=credentials,
            destination_policy=destination_policy,
            provider_id=provider.id,
            **settings,
        )
    if adapter_type == "ogc-features":
        _reject_options(
            adapter_type,
            settings,
            (
                "endpoint",
                "collection_id",
                "credential",
                "credential_header",
                "credential_scheme",
            ),
        )
        return OgcFeaturesAdapter(
            get_json=json_transport,
            credentials=credentials,
            destination_policy=destination_policy,
            provider_id=provider.id,
            **settings,
        )
    if adapter_type == "plateau":
        _reject_options(
            adapter_type,
            settings,
            ("endpoint", "credential", "credential_header", "credential_scheme"),
        )
        return PlateauAdapter(
            get_json=json_transport,
            credentials=credentials,
            destination_policy=destination_policy,
            knowledge=knowledge,
            provider_id=provider.id,
            **settings,
        )
    if adapter_type == "static":
        _reject_options(adapter_type, settings, ("items",))
        items = settings.get("items")
        if not isinstance(items, Mapping):
            raise ConfigValidationError(
                "static source requires items: provide a non-empty mapping of "
                "static resource definitions"
            )
        return StaticAdapter(cast(Mapping[str, Mapping[str, Any]], items))
    if adapter_type == "search-ckan-jp":
        _reject_options(adapter_type, settings, ("endpoint",))
        return SearchCkanJpAdapter(
            get_json=json_transport,
            destination_policy=destination_policy,
            **settings,
        )
    if adapter_type == "mlit-dpf":
        _reject_options(
            adapter_type,
            settings,
            ("endpoint", "credential", "target_rules", "representations"),
        )
        return MlitDpfAdapter(
            post_json=transport.post_json,
            credentials=credentials,
            provider_id=provider.id,
            **settings,
        )
    if adapter_type == "gsi-fundamental":
        _reject_options(adapter_type, settings, ())
        return GsiFundamentalAdapter(knowledge=knowledge)
    if adapter_type == "estat-gis":
        _reject_options(adapter_type, settings, ("distributions",))
        distributions = settings.get("distributions")
        if not isinstance(distributions, list | tuple):
            raise ConfigValidationError(
                "estat-gis source requires distributions: provide an explicit "
                "machine-readable distribution index"
            )
        return EstatGisAdapter(
            cast(Iterable[Mapping[str, Any]], distributions), knowledge=knowledge
        )
    if adapter_type == "dcat":
        _reject_options(adapter_type, settings, ("catalog_uri", "serialization"))

        def get_document(uri: str) -> str:
            return transport.get_text(uri)

        def rdf_runtime() -> Any:
            return dependencies.get("rdflib")

        return DcatAdapter(
            get_document=get_document,
            rdf_runtime_factory=rdf_runtime,
            destination_policy=destination_policy,
            **settings,
        )
    if adapter_type == "odpt":
        _reject_options(
            adapter_type,
            settings,
            (
                "endpoint",
                "resource_types",
                "filter_fields",
                "spec_source",
                "terms_url",
            ),
        )
        return OdptAdapter(**settings)
    raise AdapterRegistrationError(  # pragma: no cover
        f"Built-in source adapter {adapter_type!r} is not supported"
    )


def _reject_options(
    adapter_type: str, settings: Mapping[str, Any], allowed: tuple[str, ...]
) -> None:
    unknown = sorted(set(settings) - set(allowed))
    if unknown:
        raise ConfigValidationError(
            f"Unknown {adapter_type} source options: {', '.join(unknown)}; "
            "remove them or use the adapter's documented settings"
        )


def _split_definitions(
    definitions: Iterable[AdapterDefinition],
) -> tuple[
    tuple[SourceAdapterDefinition, ...],
    tuple[ExecutionAdapterDefinition, ...],
    tuple[KnowledgeAdapterDefinition, ...],
]:
    source_definitions: list[SourceAdapterDefinition] = []
    execution_definitions: list[ExecutionAdapterDefinition] = []
    knowledge_definitions: list[KnowledgeAdapterDefinition] = []
    for definition in definitions:
        candidate = cast(Any, definition)
        if isinstance(candidate, SourceAdapterDefinition):
            source_definitions.append(candidate)
        elif isinstance(candidate, ExecutionAdapterDefinition):
            execution_definitions.append(candidate)
        elif isinstance(candidate, KnowledgeAdapterDefinition):
            knowledge_definitions.append(candidate)
        else:
            raise AdapterRegistrationError(
                "Unknown adapter definition; expected a SourceAdapterDefinition, "
                "ExecutionAdapterDefinition, or KnowledgeAdapterDefinition"
            )
    return (
        tuple(source_definitions),
        tuple(execution_definitions),
        tuple(knowledge_definitions),
    )


def _source_definitions(
    custom_definitions: Iterable[SourceAdapterDefinition],
) -> Mapping[str, SourceAdapterDefinition]:
    def built_in_definition(adapter_type: str) -> SourceAdapterDefinition:
        return SourceAdapterDefinition(
            adapter_type,
            lambda provider, context: _build_builtin_source_adapter(
                provider,
                cast(DependencyRegistry, context.dependencies),
                cast(CredentialRegistry, context.credentials),
                context.destination_policy,
                cast(KnowledgeAdapterRegistry, context.knowledge),
                context.transport,
            ),
            dependencies=(
                frozenset({"rdflib"}) if adapter_type == "dcat" else frozenset()
            ),
        )

    definitions = {
        "direct": SourceAdapterDefinition(
            "direct", lambda provider, context: DirectAdapter()
        ),
        **{
            adapter_type: built_in_definition(adapter_type)
            for adapter_type in (
                "ckan",
                "stac",
                "ogc-features",
                "plateau",
                "static",
                "search-ckan-jp",
                "mlit-dpf",
                "gsi-fundamental",
                "dcat",
                "odpt",
                "estat-gis",
            )
        },
    }
    custom_types: set[str] = set()
    for definition in custom_definitions:
        if definition.adapter_type in custom_types:
            raise AdapterRegistrationError(
                f"Source adapter {definition.adapter_type!r} is registered more "
                "than once; adapter_type must be unique"
            )
        if definition.adapter_type in definitions:
            raise AdapterRegistrationError(
                f"Source adapter {definition.adapter_type!r} is registered more "
                "than once; built-in adapter types cannot be replaced"
            )
        custom_types.add(definition.adapter_type)
        definitions[definition.adapter_type] = definition
    return definitions


def _validate_mlit_dpf_targets(sources: tuple[Provider, ...]) -> None:
    configured_ids = {"direct", *(source.id for source in sources)}
    adapter_types = {source.id: source.adapter_type for source in sources}
    for source in sources:
        if source.adapter_type != "mlit-dpf":
            continue
        rules = source.settings.get("target_rules", ())
        if not isinstance(rules, list | tuple):
            continue
        for value in cast(list[Any] | tuple[Any, ...], rules):
            if not isinstance(value, Mapping):
                continue
            rule = cast(Mapping[str, Any], value)
            target = rule.get("source_id")
            if isinstance(target, str) and target not in configured_ids:
                raise ConfigValidationError(
                    f"mlit-dpf target rule names unconfigured source {target!r}; "
                    "add a Provider with that id"
                )
            if target == "direct":
                raise ConfigValidationError(
                    "mlit-dpf target rule must not target direct; configure "
                    "representations for the explicit Direct fallback"
                )
            if target == source.id:
                raise ConfigValidationError(
                    "mlit-dpf target rule must not delegate back to itself"
                )
            if isinstance(target, str) and adapter_types.get(target) in {
                "mlit-dpf",
                "search-ckan-jp",
            }:
                raise ConfigValidationError(
                    "mlit-dpf target rule must not target a discovery-only Provider"
                )


def _source_context(
    provider: Provider,
    definitions: Mapping[str, SourceAdapterDefinition],
    dependencies: DependencyRegistry,
    knowledge: KnowledgeAdapterRegistry,
    credentials: CredentialRegistry,
    destination_policy: DestinationPolicy,
) -> SourceAdapterContext:
    try:
        definition = definitions[provider.adapter_type]
    except KeyError:
        raise AdapterRegistrationError(
            f"Source adapter {provider.adapter_type!r} is not registered; add a "
            "matching SourceAdapterDefinition"
        ) from None
    return SourceAdapterContext(
        transport=_source_transport(provider, destination_policy),
        credentials=credentials,
        dependencies=dependencies.scoped(definition.dependencies),
        knowledge=knowledge,
        destination_policy=destination_policy,
        provider_id=provider.id,
    )


def _execution_definitions(
    custom_definitions: Iterable[ExecutionAdapterDefinition],
) -> tuple[ExecutionAdapterDefinition, ...]:
    built_in_definitions = (
        ExecutionAdapterDefinition(
            "gdal", lambda context: GdalAdapter(context.destination_policy)
        ),
        ExecutionAdapterDefinition(
            "rasterio", lambda context: RasterioAdapter(context.destination_policy)
        ),
        ExecutionAdapterDefinition(
            "pyogrio", lambda context: PyogrioAdapter(context.destination_policy)
        ),
        ExecutionAdapterDefinition(
            "json-service",
            lambda context: JsonServiceAdapter(
                OdptAdapter.prepare_request,
                "odpt",
                credentials=cast(CredentialRegistry, context.credentials),
                destination_policy=context.destination_policy,
            ),
        ),
    )
    names = {definition.name for definition in built_in_definitions}
    definitions = list(built_in_definitions)
    for definition in custom_definitions:
        if definition.name in names:
            raise AdapterRegistrationError(
                f"Execution adapter {definition.name!r} is registered more than "
                "once; adapter names must be unique"
            )
        names.add(definition.name)
        definitions.append(definition)
    return tuple(definitions)


def _knowledge_definitions(
    custom_definitions: Iterable[KnowledgeAdapterDefinition],
) -> tuple[KnowledgeAdapterDefinition, ...]:
    """Return built-in knowledge definitions plus user replacements."""
    custom_definitions_tuple = tuple(custom_definitions)
    custom_by_kind: dict[str, KnowledgeAdapterDefinition] = {}
    for definition in custom_definitions_tuple:
        if definition.kind in custom_by_kind:
            raise AdapterRegistrationError(
                f"Knowledge adapter kind {definition.kind!r} is registered more "
                "than once; provide one definition per kind"
            )
        custom_by_kind[definition.kind] = definition

    built_in_definitions = (
        KnowledgeAdapterDefinition(
            "japan-administrative-area",
            lambda _context: StaticAdministrativeAreaAdapter(
                JAPAN_ADMINISTRATIVE_AREAS
            ),
            "area",
        ),
        KnowledgeAdapterDefinition(
            "standard-time",
            lambda _context: StandardTimeAdapter(),
            "time",
        ),
    )
    built_in_kinds = frozenset(definition.kind for definition in built_in_definitions)
    definitions = [
        custom_by_kind.get(definition.kind, definition)
        for definition in built_in_definitions
    ]
    definitions.extend(
        definition
        for definition in custom_definitions_tuple
        if definition.kind not in built_in_kinds
    )
    return tuple(definitions)


def _build_source_adapter(
    source: Provider,
    definitions: Mapping[str, SourceAdapterDefinition] | DependencyRegistry,
    context: SourceAdapterContext | CredentialRegistry,
    destination_policy: DestinationPolicy | None = None,
) -> Any:
    # Keep the old private composition helper usable for downstream tests and
    # integrations while the public path uses Definition + Context.
    if isinstance(definitions, DependencyRegistry):
        return _build_builtin_source_adapter(
            source,
            definitions,
            context
            if isinstance(context, CredentialRegistry)
            else CredentialRegistry({}),
            destination_policy=destination_policy,
        )
    try:
        definition = definitions[source.adapter_type]
    except KeyError:
        raise AdapterRegistrationError(
            f"Source adapter {source.adapter_type!r} is not registered; add a "
            "matching SourceAdapterDefinition"
        ) from None
    return definition.factory(source, cast(SourceAdapterContext, context))
