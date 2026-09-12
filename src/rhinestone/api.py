"""Public composition API."""

from dataclasses import replace
from datetime import datetime
from typing import (
    Any,
    Callable,
    FrozenSet,
    Iterable,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

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
from .adapters.source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    GsiFundamentalAdapter,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    SearchCkanJpAdapter,
    StacAdapter,
    StaticAdapter,
)
from .catalogs import Catalog
from .errors import AdapterRegistrationError, ConfigValidationError
from .execution import ExecutionAdapterSelector
from .models import (
    Config,
    DependencyValue,
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
        self, source_id: str, adapter: ProviderAdapter, adapter_type: str | None = None
    ) -> None:
        self.source_id = source_id
        self.adapter_type = adapter_type or adapter.adapter_type
        self.searchable = callable(getattr(adapter, "search", None))
        empty_conditions: FrozenSet[str] = frozenset()
        self.search_conditions = cast(
            FrozenSet[str], getattr(adapter, "search_conditions", empty_conditions)
        )
        self.required_search_conditions = cast(
            FrozenSet[str],
            getattr(adapter, "required_search_conditions", empty_conditions),
        )
        self._adapter = adapter

    def load(self, config: Config) -> Source:
        source = self._adapter.load(Config(self.adapter_type, config.settings))
        return replace(
            source,
            provenance=replace(source.provenance, provider=self.source_id),
        )

    def search(self, query: SearchQuery) -> Tuple[Result, ...]:
        search_method = getattr(self._adapter, "search")
        search = cast(Callable[[SearchQuery], Tuple[Result, ...]], search_method)
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
            for result in search(query)
        )


class Rhinestone:
    """An isolated context composed from sources and user-owned runtime inputs."""

    def __init__(
        self,
        *,
        sources: Iterable[Provider] = (),
        catalog: Optional[Catalog] = None,
        dependencies: Optional[Mapping[str, DependencyValue]] = None,
        credentials: Optional[Mapping[str, Callable[[], str]]] = None,
        network_policy: NetworkPolicyLevel = "credentialed",
        adapters: Iterable[AdapterDefinition] = (),
    ) -> None:
        selected_sources = tuple(sources)
        if catalog is not None:
            if selected_sources:
                raise TypeError("pass either catalog or sources, not both")
            selected_sources = tuple(catalog)

        custom_source_definitions, custom_execution_definitions = _split_definitions(
            adapters
        )
        source_definitions = _source_definitions(custom_source_definitions)
        execution_definitions = _execution_definitions(custom_execution_definitions)
        execution_runtime_names = frozenset(
            definition.name for definition in execution_definitions
        )
        runtime_dependencies = dict(dependencies or {})
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
                        runtime_dependencies,
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
                    f"Source {source_id!r} is registered more than once"
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
                            runtime_dependencies,
                            credential_registry,
                            destination_policy,
                        ),
                    ),
                    source_definition.adapter_type,
                )
            )

        source_adapters: Tuple[Any, ...] = tuple(configured_sources)

        def bind(adapter: Any) -> Any:
            binder = getattr(adapter, "bind_credentials", None)
            return binder(credential_registry) if callable(binder) else adapter

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
                    f"expected {definition.name!r}"
                )
            configured_executions.append(execution)
        adapter_registry = AdapterRegistry(
            source_adapters, (bind(adapter) for adapter in configured_executions)
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
        self._search = SearchCoordinator(source_adapters)

    def resolve(self, value: Union[Config, Result]) -> Resource:
        """Resolve a Provider selection or a search Result into a Resource."""
        if not isinstance(value, Result):
            return self._pipeline.resolve(value)
        resource = self._pipeline.resolve(value.to_config())
        if value.discovered_by == value.target.source_id:
            return resource
        source = replace(
            resource.source,
            metadata=value.metadata,
            provenance=value.provenance,
        )
        return replace(
            resource,
            metadata=value.metadata,
            provenance=value.provenance,
            source=source,
        )

    def open(
        self, value: Union[Config, Result, Resource], library: LibraryName
    ) -> object:
        """Open a Resource, or resolve a Config/Result and open it."""
        if isinstance(value, Resource):
            return self._pipeline.open_resource(value, library)
        if isinstance(value, Config):
            return self._pipeline.open(value, library=library)
        return self.resolve(value).open(library)

    def search(
        self,
        query: Optional[Union[SearchQuery, str]] = None,
        *,
        text: Optional[str] = None,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        time: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None,
        limit: Optional[int] = None,
    ) -> SearchResults:
        supplied_parameters = (text, bbox, time, limit)
        if query is not None and any(
            parameter is not None for parameter in supplied_parameters
        ):
            raise TypeError("pass either query or search parameters, not both")
        if query is None:
            normalized_query = SearchQuery(text=text, bbox=bbox, time=time, limit=limit)
        elif isinstance(query, str):
            normalized_query = SearchQuery(text=query)
        else:
            normalized_query = query
        return self._search.search(normalized_query).bind_resolver(self.resolve)


def configure(
    *,
    sources: Iterable[Provider] = (),
    catalog: Optional[Catalog] = None,
    dependencies: Optional[Mapping[str, DependencyValue]] = None,
    credentials: Optional[Mapping[str, Callable[[], str]]] = None,
    network_policy: NetworkPolicyLevel = "credentialed",
    adapters: Iterable[AdapterDefinition] = (),
) -> Rhinestone:
    """Compose built-in adapters around selected sources and runtime inputs."""
    return Rhinestone(
        sources=sources,
        catalog=catalog,
        dependencies=dependencies,
        credentials=credentials,
        network_policy=network_policy,
        adapters=adapters,
    )


def _build_builtin_source_adapter(
    source: Provider,
    dependencies: DependencyRegistry,
    credentials: CredentialRegistry,
    destination_policy: Optional[DestinationPolicy] = None,
) -> ProviderAdapter:
    adapter_type = source.adapter_type
    settings = dict(source.settings)

    def json_transport(
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        return _http.get_json(url, params, headers)

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
            provider_id=source.id,
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
            provider_id=source.id,
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
            provider_id=source.id,
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
            provider_id=source.id,
            **settings,
        )
    if adapter_type == "static":
        _reject_options(adapter_type, settings, ("items",))
        items = settings.get("items")
        if not isinstance(items, Mapping):
            raise ConfigValidationError("static source requires items")
        return StaticAdapter(cast(Mapping[str, Mapping[str, Any]], items))
    if adapter_type == "search-ckan-jp":
        _reject_options(adapter_type, settings, ("endpoint",))
        return SearchCkanJpAdapter(
            get_json=json_transport,
            destination_policy=destination_policy,
            **settings,
        )
    if adapter_type == "gsi-fundamental":
        _reject_options(adapter_type, settings, ())
        return GsiFundamentalAdapter()
    if adapter_type == "dcat":
        _reject_options(adapter_type, settings, ("catalog_uri", "serialization"))

        def get_document(uri: str) -> str:
            return _http.get_text(uri)

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
    adapter_type: str, settings: Mapping[str, Any], allowed: Tuple[str, ...]
) -> None:
    unknown = sorted(set(settings) - set(allowed))
    if unknown:
        raise ConfigValidationError(
            f"Unknown {adapter_type} source options: {', '.join(unknown)}"
        )


def _split_definitions(
    definitions: Iterable[AdapterDefinition],
) -> Tuple[Tuple[SourceAdapterDefinition, ...], Tuple[ExecutionAdapterDefinition, ...]]:
    sources: list[SourceAdapterDefinition] = []
    executions: list[ExecutionAdapterDefinition] = []
    for definition in definitions:
        candidate = cast(Any, definition)
        if isinstance(candidate, SourceAdapterDefinition):
            sources.append(candidate)
        elif isinstance(candidate, ExecutionAdapterDefinition):
            executions.append(candidate)
        else:
            raise AdapterRegistrationError("Unknown adapter definition")
    return tuple(sources), tuple(executions)


def _source_definitions(
    custom: Iterable[SourceAdapterDefinition],
) -> Mapping[str, SourceAdapterDefinition]:
    def builtin(adapter_type: str) -> SourceAdapterDefinition:
        return SourceAdapterDefinition(
            adapter_type,
            lambda provider, context: _build_builtin_source_adapter(
                provider,
                context.dependencies,
                context.credentials,
                context.destination_policy,
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
            adapter_type: builtin(adapter_type)
            for adapter_type in (
                "ckan",
                "stac",
                "ogc-features",
                "plateau",
                "static",
                "search-ckan-jp",
                "gsi-fundamental",
                "dcat",
                "odpt",
            )
        },
    }
    custom_types: set[str] = set()
    for definition in custom:
        if definition.adapter_type in custom_types:
            raise AdapterRegistrationError(
                f"Source adapter {definition.adapter_type!r} is registered more than once"
            )
        if definition.adapter_type in definitions:
            raise AdapterRegistrationError(
                f"Source adapter {definition.adapter_type!r} is registered more than once"
            )
        custom_types.add(definition.adapter_type)
        definitions[definition.adapter_type] = definition
    return definitions


def _source_context(
    provider: Provider,
    definitions: Mapping[str, SourceAdapterDefinition],
    runtime_dependencies: Mapping[str, DependencyValue],
    credentials: CredentialRegistry,
    destination_policy: DestinationPolicy,
) -> SourceAdapterContext:
    try:
        definition = definitions[provider.adapter_type]
    except KeyError:
        raise AdapterRegistrationError(
            f"Source adapter {provider.adapter_type!r} is not registered"
        ) from None
    dependencies = DependencyRegistry(
        {
            name: runtime_dependencies[name]
            for name in definition.dependencies
            if name in runtime_dependencies
        }
    )
    return SourceAdapterContext(
        get_json=_http.get_json,
        get_text=_http.get_text,
        credentials=credentials,
        dependencies=dependencies,
        destination_policy=destination_policy,
        provider_id=provider.id,
    )


def _execution_definitions(
    custom: Iterable[ExecutionAdapterDefinition],
) -> Tuple[ExecutionAdapterDefinition, ...]:
    preinstalled = (
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
                credentials=context.credentials,
                destination_policy=context.destination_policy,
            ),
        ),
    )
    names = {definition.name for definition in preinstalled}
    definitions = list(preinstalled)
    for definition in custom:
        if definition.name in names:
            raise AdapterRegistrationError(
                f"Execution adapter {definition.name!r} is registered more than once"
            )
        names.add(definition.name)
        definitions.append(definition)
    return tuple(definitions)


def _build_source_adapter(
    source: Provider,
    definitions: Mapping[str, SourceAdapterDefinition] | DependencyRegistry,
    context: SourceAdapterContext | CredentialRegistry,
    destination_policy: Optional[DestinationPolicy] = None,
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
            destination_policy,
        )
    try:
        definition = definitions[source.adapter_type]
    except KeyError:
        raise AdapterRegistrationError(
            f"Source adapter {source.adapter_type!r} is not registered"
        ) from None
    return definition.factory(source, cast(SourceAdapterContext, context))
