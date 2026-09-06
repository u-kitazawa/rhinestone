"""Public composition API."""

from dataclasses import replace
from typing import Any, Callable, Dict, FrozenSet, Mapping, Optional, Tuple, cast

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
    GsiTileAdapter,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    StacAdapter,
)
from .adapters.source.estat import DEFAULT_ENDPOINT as ESTAT_ENDPOINT
from .errors import AdapterRegistrationError, ConfigValidationError
from .execution import ExecutionAdapterSelector
from .models import Config, ProviderConfig, Resource, SearchQuery, SearchResult, Source
from .pipeline import AccessPipeline
from .registry import AdapterRegistry, CredentialRegistry, DependencyRegistry
from .resolution import Resolver
from .search import SearchCoordinator

Factory = Callable[[], Any]


class _ConfiguredProviderAdapter:
    """Bind one provider id to one built-in adapter instance."""

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
    """An isolated context composed from providers and user-owned dependencies."""

    def __init__(
        self,
        *,
        providers: Optional[Mapping[str, ProviderConfig]] = None,
        dependencies: Optional[Mapping[str, Factory]] = None,
        credentials: Optional[Mapping[str, Callable[[], str]]] = None,
    ) -> None:
        dependency_registry = DependencyRegistry(dependencies or {})
        credential_registry = CredentialRegistry(credentials or {})
        configured: Dict[str, ProviderConfig] = {"direct": ProviderConfig("direct")}
        for source_id, provider in (providers or {}).items():
            if not source_id:
                raise AdapterRegistrationError("Provider id must be non-empty")
            if source_id in configured:
                raise AdapterRegistrationError(
                    f"Provider {source_id!r} is registered more than once"
                )
            configured[source_id] = provider

        sources = tuple(
            _ConfiguredProviderAdapter(
                source_id,
                _build_source_adapter(provider, dependency_registry),
            )
            for source_id, provider in configured.items()
        )
        executions = (
            GdalAdapter(),
            RasterioAdapter(),
            PyogrioAdapter(),
            JsonServiceAdapter(OdptAdapter.prepare_request, "odpt"),
        )

        def bind(adapter: Any) -> Any:
            binder = getattr(adapter, "bind_credentials", None)
            return binder(credential_registry) if callable(binder) else adapter

        adapters = AdapterRegistry(sources, (bind(adapter) for adapter in executions))
        self._pipeline = AccessPipeline(
            adapter_registry=adapters,
            resolver=Resolver(),
            execution_selector=ExecutionAdapterSelector(adapters.execution_adapters),
            dependencies=dependency_registry,
        )
        self._search = SearchCoordinator(sources)

    def resolve(self, config: Config) -> Resource:
        return self._pipeline.resolve(config)

    def open(self, config: Config, adapter: Optional[str] = None) -> Any:
        return self._pipeline.open(config, adapter=adapter)

    def search(self, query: SearchQuery) -> Mapping[str, Tuple[SearchResult, ...]]:
        return self._search.search(query)


def configure(
    *,
    providers: Optional[Mapping[str, ProviderConfig]] = None,
    dependencies: Optional[Mapping[str, Factory]] = None,
    credentials: Optional[Mapping[str, Callable[[], str]]] = None,
) -> Rhinestone:
    """Compose built-in adapters around named providers and lazy dependencies."""
    return Rhinestone(
        providers=providers,
        dependencies=dependencies,
        credentials=credentials,
    )


def _build_source_adapter(
    provider: ProviderConfig, dependencies: DependencyRegistry
) -> ProviderAdapter:
    adapter_type = provider.adapter_type
    settings = dict(provider.settings)

    def json_transport(
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        get_json = dependencies.get("http-json")
        if headers:
            return get_json(url, params, headers)
        return get_json(url, params)

    if adapter_type == "direct":
        _reject_options(adapter_type, settings, ())
        return DirectAdapter()
    if adapter_type == "ckan":
        _reject_options(
            adapter_type,
            settings,
            ("endpoint", "api_token", "api_key", "api_key_header"),
        )
        return CkanAdapter(get_json=json_transport, **settings)
    if adapter_type == "estat":
        _reject_options(
            adapter_type,
            settings,
            ("app_id", "api_key", "endpoint", "language"),
        )
        settings.setdefault("endpoint", ESTAT_ENDPOINT)
        return EStatAdapter(get_json=json_transport, **settings)
    if adapter_type == "stac":
        _reject_options(
            adapter_type,
            settings,
            ("endpoint", "api_token", "api_key", "api_key_header"),
        )
        return StacAdapter(get_json=json_transport, **settings)
    if adapter_type == "ogc-features":
        _reject_options(
            adapter_type,
            settings,
            (
                "endpoint",
                "collection_id",
                "api_token",
                "api_key",
                "api_key_header",
            ),
        )
        return OgcFeaturesAdapter(get_json=json_transport, **settings)
    if adapter_type == "plateau":
        _reject_options(adapter_type, settings, ("endpoint",))
        return PlateauAdapter(get_json=json_transport, **settings)
    if adapter_type == "gsi-tile":
        _reject_options(adapter_type, settings, ())
        return GsiTileAdapter()
    if adapter_type == "gsi-fundamental":
        _reject_options(adapter_type, settings, ())
        return GsiFundamentalAdapter()
    if adapter_type == "dcat":
        _reject_options(adapter_type, settings, ("catalog_uri", "serialization"))

        def get_document(uri: str) -> str:
            return cast(str, dependencies.get("http-text")(uri))

        def rdf_runtime() -> Any:
            return dependencies.get("rdflib")

        return DcatAdapter(
            get_document=get_document,
            rdf_runtime_factory=rdf_runtime,
            **settings,
        )
    if adapter_type == "odpt":
        _reject_options(adapter_type, settings, ())
        return OdptAdapter()
    raise AdapterRegistrationError(
        f"Built-in source adapter {adapter_type!r} is not supported"
    )


def _reject_options(
    adapter_type: str, settings: Mapping[str, Any], allowed: Tuple[str, ...]
) -> None:
    unknown = sorted(set(settings) - set(allowed))
    if unknown:
        raise ConfigValidationError(
            f"Unknown {adapter_type} provider options: {', '.join(unknown)}"
        )
