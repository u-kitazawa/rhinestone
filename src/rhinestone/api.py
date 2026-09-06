"""Public composition API."""

from dataclasses import replace
from typing import Any, Callable, FrozenSet, Iterable, Mapping, Optional, Tuple, Union, cast

from . import _http
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
    EStatAdapter,
    GsiFundamentalAdapter,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    StacAdapter,
    StaticAdapter,
)
from .errors import AdapterRegistrationError, ConfigValidationError
from .execution import ExecutionAdapterSelector
from .models import (
    Config,
    Dependencies,
    LibraryName,
    Resource,
    SearchQuery,
    SearchResult,
    Source,
    SourceDefinition,
)
from .pipeline import AccessPipeline
from .registry import AdapterRegistry, CredentialRegistry, DependencyRegistry
from .resolution import Resolver
from .search import SearchCoordinator, SearchResults


class _ConfiguredSourceAdapter:
    """Bind one public source id to one built-in adapter instance."""

    def __init__(self, source_id: str, adapter: ProviderAdapter) -> None:
        self.source_id = source_id
        self.adapter_type = adapter.adapter_type
        self.searchable = callable(getattr(adapter, "search", None))
        empty_conditions: FrozenSet[str] = frozenset()
        self.search_conditions = cast(
            FrozenSet[str], getattr(adapter, "search_conditions", empty_conditions)
        )
        self._adapter = adapter

    def load(self, config: Config) -> Source:
        source = self._adapter.load(Config(self.adapter_type, config.settings))
        return replace(
            source,
            provenance=replace(source.provenance, provider=self.source_id),
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        search_method = getattr(self._adapter, "search")
        search = cast(Callable[[SearchQuery], Tuple[SearchResult, ...]], search_method)
        return tuple(
            replace(
                result,
                source_id=self.source_id,
                provenance=replace(result.provenance, provider=self.source_id),
            )
            for result in search(query)
        )


class Rhinestone:
    """An isolated context composed from sources and user-owned runtime inputs."""

    def __init__(
        self,
        *,
        sources: Iterable[SourceDefinition] = (),
        dependencies: Optional[Dependencies] = None,
        credentials: Optional[Mapping[str, Callable[[], str]]] = None,
    ) -> None:
        runtime_dependencies = dict(dependencies or {})
        runtime_dependencies.setdefault(
            "json-service", lambda: _http.JsonServiceRuntime()
        )
        dependency_registry = DependencyRegistry(runtime_dependencies)
        credential_registry = CredentialRegistry(credentials or {})

        configured_sources = [_ConfiguredSourceAdapter("direct", DirectAdapter())]
        configured_ids = {"direct"}
        for source_definition in sources:
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
                        dependency_registry,
                        credential_registry,
                    ),
                )
            )

        source_adapters = tuple(configured_sources)
        executions = (
            GdalAdapter(),
            RasterioAdapter(),
            PyogrioAdapter(),
            JsonServiceAdapter(OdptAdapter.prepare_request, "odpt"),
        )

        def bind(adapter: Any) -> Any:
            binder = getattr(adapter, "bind_credentials", None)
            return binder(credential_registry) if callable(binder) else adapter

        adapters = AdapterRegistry(
            source_adapters, (bind(adapter) for adapter in executions)
        )
        self._pipeline = AccessPipeline(
            adapter_registry=adapters,
            resolver=Resolver(),
            execution_selector=ExecutionAdapterSelector(adapters.execution_adapters),
            dependencies=dependency_registry,
        )
        self._search = SearchCoordinator(source_adapters)

    def resolve(self, config: Config) -> Resource:
        return self._pipeline.resolve(config)

    def open(self, config: Config, library: LibraryName) -> object:
        return self._pipeline.open(config, library=library)

    def search(self, query: Union[SearchQuery, str]) -> SearchResults:
        normalized_query = (
            SearchQuery(text=query) if isinstance(query, str) else query
        )
        grouped = self._search.search(normalized_query)
        typed_grouped = cast(
            Mapping[str, Tuple[SearchResult, ...]],
            grouped,
        )
        return SearchResults.from_grouped(typed_grouped).bind_resolver(self.resolve)


def configure(
    *,
    sources: Iterable[SourceDefinition] = (),
    dependencies: Optional[Dependencies] = None,
    credentials: Optional[Mapping[str, Callable[[], str]]] = None,
) -> Rhinestone:
    """Compose built-in adapters around selected sources and runtime inputs."""
    return Rhinestone(
        sources=sources,
        dependencies=dependencies,
        credentials=credentials,
    )


def _build_source_adapter(
    source: SourceDefinition,
    dependencies: DependencyRegistry,
    credentials: CredentialRegistry,
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
        _reject_options(adapter_type, settings, ("endpoint",))
        return CkanAdapter(get_json=json_transport, **settings)
    if adapter_type == "estat":
        _reject_options(adapter_type, settings, ("endpoint", "language"))
        return EStatAdapter(
            get_json=json_transport,
            credential_factory=lambda: credentials.get("estat"),
            **settings,
        )
    if adapter_type == "stac":
        _reject_options(adapter_type, settings, ("endpoint",))
        return StacAdapter(get_json=json_transport, **settings)
    if adapter_type == "ogc-features":
        _reject_options(adapter_type, settings, ("endpoint", "collection_id"))
        return OgcFeaturesAdapter(get_json=json_transport, **settings)
    if adapter_type == "plateau":
        _reject_options(adapter_type, settings, ("endpoint",))
        return PlateauAdapter(get_json=json_transport, **settings)
    if adapter_type == "static":
        _reject_options(adapter_type, settings, ("items",))
        items = settings.get("items")
        if not isinstance(items, Mapping):
            raise ConfigValidationError("static source requires items")
        return StaticAdapter(cast(Mapping[str, Mapping[str, Any]], items))
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
    raise AdapterRegistrationError(
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
