"""Internal composition of built-in and custom adapters."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from typing import Any, cast

from . import _http
from .adapters.contracts import (
    AdapterDefinition,
    ExecutionAdapterDefinition,
    SearchableSourceAdapter,
    SourceAdapter,
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
    KnowledgeAdapterDefinition,
    KnowledgeAdapterRegistry,
    StandardTimeAdapter,
    StaticAdministrativeAreaAdapter,
)
from .adapters.knowledge._japan_administrative_areas import (
    JAPAN_ADMINISTRATIVE_AREAS,
)
from .adapters.source import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    EstatGisAdapter,
    GeospatialJpAdapter,
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
from .errors import (
    AdapterRegistrationError,
    ConfigValidationError,
    ProviderMetadataError,
)
from .models import (
    Config,
    Provider,
    ProviderSearchResults,
    Result,
    SearchQuery,
    Source,
)
from .registry import CredentialRegistry, DependencyRegistry
from .security import DestinationPolicy


class ConfiguredSourceAdapter:
    """Bind one public source id to one built-in adapter instance."""

    def __init__(
        self,
        source_id: str,
        source_adapter: SourceAdapter,
        adapter_type: str,
    ) -> None:
        self.source_id = source_id
        self.adapter_type = adapter_type
        self.searchable = isinstance(source_adapter, SearchableSourceAdapter)
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

    def search(self, query: SearchQuery) -> tuple[Result, ...] | ProviderSearchResults:
        source_adapter = cast(SearchableSourceAdapter, self._source_adapter)
        raw_results = source_adapter.search(query)
        mapped_results = tuple(
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
            for result in raw_results
        )
        if not isinstance(raw_results, ProviderSearchResults):
            return mapped_results
        return ProviderSearchResults(
            mapped_results,
            tuple(
                replace(diagnostic, source_id=self.source_id)
                for diagnostic in raw_results.diagnostics
            ),
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


def _settings(provider: Provider, allowed: tuple[str, ...]) -> dict[str, Any]:
    settings = dict(provider.settings)
    _reject_options(provider.adapter_type, settings, allowed)
    return settings


def _json_transport(context: SourceAdapterContext) -> Any:
    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        return context.transport.get_json(url, params, headers)

    return get_json


def _build_ckan(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    return CkanAdapter(
        get_json=_json_transport(context),
        credentials=cast(CredentialRegistry, context.credentials),
        destination_policy=context.destination_policy,
        provider_id=provider.id,
        **_settings(
            provider,
            (
                "endpoint",
                "spatial_search",
                "credential",
                "credential_header",
                "credential_scheme",
            ),
        ),
    )


def _build_geospatial_jp(
    provider: Provider, context: SourceAdapterContext
) -> ProviderAdapter:
    return GeospatialJpAdapter(
        get_json=_json_transport(context),
        credentials=cast(CredentialRegistry, context.credentials),
        destination_policy=context.destination_policy,
        provider_id=provider.id,
        **_settings(
            provider,
            ("endpoint", "credential", "credential_header", "credential_scheme"),
        ),
    )


def _build_stac(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    return StacAdapter(
        get_json=_json_transport(context),
        credentials=cast(CredentialRegistry, context.credentials),
        destination_policy=context.destination_policy,
        provider_id=provider.id,
        **_settings(
            provider,
            ("endpoint", "credential", "credential_header", "credential_scheme"),
        ),
    )


def _build_ogc(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    return OgcFeaturesAdapter(
        get_json=_json_transport(context),
        credentials=cast(CredentialRegistry, context.credentials),
        destination_policy=context.destination_policy,
        provider_id=provider.id,
        **_settings(
            provider,
            (
                "endpoint",
                "collection_id",
                "credential",
                "credential_header",
                "credential_scheme",
            ),
        ),
    )


def _build_plateau(
    provider: Provider, context: SourceAdapterContext
) -> ProviderAdapter:
    return PlateauAdapter(
        get_json=_json_transport(context),
        credentials=cast(CredentialRegistry, context.credentials),
        destination_policy=context.destination_policy,
        knowledge=cast(KnowledgeAdapterRegistry, context.knowledge),
        provider_id=provider.id,
        **_settings(
            provider,
            ("endpoint", "credential", "credential_header", "credential_scheme"),
        ),
    )


def _build_static(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    items = _settings(provider, ("items",)).get("items")
    if not isinstance(items, Mapping):
        raise ConfigValidationError(
            "static source requires items: provide a non-empty mapping of "
            "static resource definitions"
        )
    return StaticAdapter(cast(Mapping[str, Mapping[str, Any]], items))


def _build_search_ckan_jp(
    provider: Provider, context: SourceAdapterContext
) -> ProviderAdapter:
    return SearchCkanJpAdapter(
        get_json=_json_transport(context),
        destination_policy=context.destination_policy,
        **_settings(provider, ("endpoint",)),
    )


def _build_mlit_dpf(
    provider: Provider, context: SourceAdapterContext
) -> ProviderAdapter:
    return MlitDpfAdapter(
        post_json=context.transport.post_json,
        credentials=cast(CredentialRegistry, context.credentials),
        provider_id=provider.id,
        **_settings(
            provider, ("endpoint", "credential", "target_rules", "representations")
        ),
    )


def _build_gsi(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    _settings(provider, ())
    return GsiFundamentalAdapter(
        knowledge=cast(KnowledgeAdapterRegistry, context.knowledge)
    )


def _build_estat(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    distributions = _settings(provider, ("distributions",)).get("distributions")
    if not isinstance(distributions, list | tuple):
        raise ConfigValidationError(
            "estat-gis source requires distributions: provide an explicit "
            "machine-readable distribution index"
        )
    return EstatGisAdapter(
        cast(Iterable[Mapping[str, Any]], distributions),
        knowledge=cast(KnowledgeAdapterRegistry, context.knowledge),
    )


def _build_dcat(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    settings = _settings(provider, ("catalog_uri", "serialization"))

    def get_document(uri: str) -> str:
        return context.transport.get_text(uri)

    def rdf_runtime() -> Any:
        return context.dependencies.get("rdflib")

    return DcatAdapter(
        get_document=get_document,
        rdf_runtime_factory=rdf_runtime,
        destination_policy=context.destination_policy,
        **settings,
    )


def _build_odpt(provider: Provider, context: SourceAdapterContext) -> ProviderAdapter:
    return OdptAdapter(
        **_settings(
            provider,
            ("endpoint", "resource_types", "filter_fields", "spec_source", "terms_url"),
        )
    )


BUILTIN_SOURCE_ADAPTER_FACTORIES: Mapping[
    str, Callable[[Provider, SourceAdapterContext], ProviderAdapter]
] = {
    "direct": lambda _provider, _context: DirectAdapter(),
    "ckan": _build_ckan,
    "geospatial-jp": _build_geospatial_jp,
    "stac": _build_stac,
    "ogc-features": _build_ogc,
    "plateau": _build_plateau,
    "static": _build_static,
    "search-ckan-jp": _build_search_ckan_jp,
    "mlit-dpf": _build_mlit_dpf,
    "gsi-fundamental": _build_gsi,
    "estat-gis": _build_estat,
    "dcat": _build_dcat,
    "odpt": _build_odpt,
}


def _reject_options(
    adapter_type: str, settings: Mapping[str, Any], allowed: tuple[str, ...]
) -> None:
    unknown = sorted(set(settings) - set(allowed))
    if unknown:
        raise ConfigValidationError(
            f"Unknown {adapter_type} source options: {', '.join(unknown)}; "
            "remove them or use the adapter's documented settings"
        )


def split_definitions(
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


def source_definitions(
    custom_definitions: Iterable[SourceAdapterDefinition],
) -> Mapping[str, SourceAdapterDefinition]:
    definitions = {
        adapter_type: SourceAdapterDefinition(
            adapter_type,
            factory,
            dependencies=(
                frozenset({"rdflib"}) if adapter_type == "dcat" else frozenset()
            ),
        )
        for adapter_type, factory in BUILTIN_SOURCE_ADAPTER_FACTORIES.items()
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


def validate_mlit_dpf_targets(sources: tuple[Provider, ...]) -> None:
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


def source_context(
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


def execution_definitions(
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


def knowledge_definitions(
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


def build_source_adapter(
    source: Provider,
    definitions: Mapping[str, SourceAdapterDefinition],
    context: SourceAdapterContext,
) -> SourceAdapter:
    definition = definitions[source.adapter_type]
    return definition.factory(source, context)
