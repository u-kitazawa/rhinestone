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
    SearchQuery,
    Source,
)
from .pipeline import AccessPipeline
from .registry import AdapterRegistry, CredentialRegistry, DependencyRegistry
from .resolution import Resolver
from .search import SearchCoordinator, SearchResults

_SOURCE_RUNTIME_NAMES = frozenset({"rdflib"})
_EXECUTION_RUNTIME_NAMES = frozenset({"gdal", "json-service", "rasterio", "pyogrio"})


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
    ) -> None:
        selected_sources = tuple(sources)
        if catalog is not None:
            if selected_sources:
                raise TypeError("pass either catalog or sources, not both")
            selected_sources = tuple(catalog)

        runtime_dependencies = dict(dependencies or {})
        source_dependencies = DependencyRegistry(
            {
                name: value
                for name, value in runtime_dependencies.items()
                if name in _SOURCE_RUNTIME_NAMES
            }
        )
        execution_dependencies = {
            name: value
            for name, value in runtime_dependencies.items()
            if name in _EXECUTION_RUNTIME_NAMES
        }
        execution_dependencies.setdefault(
            "json-service", lambda: _http.JsonServiceRuntime()
        )
        execution_dependency_registry = DependencyRegistry(execution_dependencies)
        credential_registry = CredentialRegistry(credentials or {})

        configured_sources = [_ConfiguredSourceAdapter("direct", DirectAdapter())]
        configured_ids = {"direct"}
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
                        source_dependencies,
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
            dependencies=execution_dependency_registry,
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
            return value.open(library)
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
) -> Rhinestone:
    """Compose built-in adapters around selected sources and runtime inputs."""
    return Rhinestone(
        sources=sources,
        catalog=catalog,
        dependencies=dependencies,
        credentials=credentials,
    )


def _build_source_adapter(
    source: Provider,
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
    if adapter_type == "search-ckan-jp":
        _reject_options(adapter_type, settings, ("endpoint",))
        return SearchCkanJpAdapter(get_json=json_transport, **settings)
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
