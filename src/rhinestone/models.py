"""Domain models, including the small public vocabulary."""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    FrozenSet,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypedDict,
    Union,
    cast,
    overload,
)

from ._uri import is_valid_http_authority
from .errors import ConfigValidationError, ExecutionAdapterUnavailableError

LibraryName = str
"""Execution runtime name accepted by the public open API."""


@dataclass(frozen=True)
class RuntimeFactory:
    """Describe a runtime factory evaluated only when its runtime is needed.

    The zero-argument callable is not evaluated during application
    configuration. Its result is cached within the configured dependency
    scope.
    """

    factory: Callable[[], Any]


DependencyValue = Union[object, RuntimeFactory]
"""An injected Runtime object or an explicit lazy RuntimeFactory."""

Runtime = DependencyValue
"""A Runtime object or an explicit lazy RuntimeFactory."""


class _RasterioDatasetReader(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class _GdalDataset(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class _GeoDataFrame(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class Dependencies(TypedDict, total=False):
    """IDE-discoverable names for supported Source and Execution runtimes."""

    gdal: DependencyValue
    """Execution Runtime used for raster, vector, and tile access."""

    rasterio: DependencyValue
    """Execution Runtime used for COG and GeoTIFF access."""

    pyogrio: DependencyValue
    """Execution Runtime used for vector data access."""

    rdflib: DependencyValue
    """Source Runtime used when searching or resolving a DCAT catalog."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return MappingProxyType({key: _freeze(item) for key, item in mapping.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in cast(List[Any], value))
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in cast(Tuple[Any, ...], value))
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in cast(Set[Any], value))
    return value


def _empty_mapping() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True)
class Provider:
    """Describe one configured data provider.

    ``id`` is the application-local identifier used by ``Config`` and search
    diagnostics. ``adapter_type`` selects the Source Adapter that interprets
    ``settings``. Runtime objects and secrets belong in ``configure`` inputs,
    not in this immutable value.
    """

    id: str
    adapter_type: str
    settings: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.id:
            raise ConfigValidationError(
                "source id must be a non-empty string; set Provider.id to the "
                "configured source identifier"
            )
        if not self.adapter_type:
            raise ConfigValidationError(
                "adapter_type must be a non-empty string; choose a "
                "registered source adapter type"
            )
        object.__setattr__(self, "settings", _freeze(self.settings))


# Advanced implementation code may use this descriptive alias.
SourceDefinition = Provider


@dataclass(frozen=True)
class Config:
    """Select one configured source and provide its resolution settings.

    ``source_id`` must refer to a Provider configured in the application;
    ``settings`` are interpreted by that source's adapter and frozen on input.
    """

    source_id: str
    settings: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ConfigValidationError(
                "source_id must be a non-empty string; identify the "
                "configured source to resolve"
            )
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True)
class Metadata:
    """Normalized human-readable metadata retained from a source response.

    Common fields support display and inspection while provider-specific values
    remain available in the immutable ``raw`` mapping.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    publisher: Optional[str] = None
    license: Optional[str] = None
    updated_at: Optional[datetime] = None
    raw: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze(self.raw))


@dataclass(frozen=True)
class Provenance:
    """Trace the provider, identifiers, endpoint, and retrieval of a value.

    Provenance is retained through search, resolution, and execution. The
    ``raw`` mapping must not contain credentials or other secrets.
    """

    provider: str
    dataset_identifier: Optional[str] = None
    resource_identifier: Optional[str] = None
    api_endpoint: Optional[str] = None
    original_url: Optional[str] = None
    query_parameters: Mapping[str, Any] = field(default_factory=_empty_mapping)
    retrieved_at: Optional[datetime] = None
    checksum: Optional[str] = None
    adapter: Optional[str] = None
    adapter_version: Optional[str] = None
    raw: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_parameters", _freeze(self.query_parameters))
        object.__setattr__(self, "raw", _freeze(self.raw))


@dataclass(frozen=True)
class DiscoveryRecord:
    """Retain the record produced by a Source that discovered a result.

    Cross-source resolution must not overwrite the metadata or provenance
    produced by the target Source.  A resolved ``Resource`` keeps its target
    record in the usual ``metadata`` / ``provenance`` fields and stores this
    discovery-side record separately.
    """

    source_id: str
    metadata: Metadata
    provenance: Provenance
    raw_metadata: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        source_id = cast(object, self.source_id)
        if not isinstance(source_id, str) or not source_id.strip():
            raise ConfigValidationError(
                "DiscoveryRecord.source_id must be a non-empty string"
            )
        object.__setattr__(self, "raw_metadata", _freeze(self.raw_metadata))

    @property
    def discovered_by(self) -> str:
        """Return the source id using the terminology of ``Result``."""
        return self.source_id


@dataclass(frozen=True)
class ResourceCandidate:
    """One provider-advertised delivery option considered by the Resolver.

    ``attributes`` carries explicit resolver hints such as ``matches_config``,
    ``access_kind``, ``access_options``, and ``archive``. Candidates are not
    opened directly; resolve the enclosing ``Source`` first.
    """

    uri: str
    format: Optional[str]
    media_type: Optional[str]
    attributes: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        uri = cast(object, self.uri)
        if not isinstance(uri, str) or not uri.strip():
            raise ConfigValidationError(
                "ResourceCandidate.uri must be a non-empty string"
            )
        if not is_valid_http_authority(uri):
            raise ConfigValidationError(
                "ResourceCandidate.uri must not contain embedded credentials or "
                "an invalid HTTP(S) authority"
            )
        for name in ("format", "media_type"):
            value = cast(object, getattr(self, name))
            if value is not None and not isinstance(value, str):
                raise ConfigValidationError(
                    f"ResourceCandidate.{name} must be a string or None"
                )
        attributes = cast(object, self.attributes)
        if not isinstance(attributes, Mapping):
            raise ConfigValidationError(
                "ResourceCandidate.attributes must be a mapping"
            )
        object.__setattr__(self, "attributes", _freeze(self.attributes))


@dataclass(frozen=True)
class Source:
    """Normalized provider output consumed by resource resolution.

    The source retains metadata, all delivery candidates, capabilities,
    provenance, and raw provider metadata for later pipeline stages.
    """

    metadata: Metadata
    candidates: Tuple[ResourceCandidate, ...]
    capabilities: FrozenSet[str]
    provenance: Provenance
    raw_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        object.__setattr__(self, "raw_metadata", _freeze(self.raw_metadata))


@dataclass(frozen=True)
class AccessPlan:
    """Explicit instructions describing how a selected resource is delivered.

    ``kind`` identifies the delivery shape and ``options`` carries safe,
    adapter-specific execution values.
    """

    kind: str
    uri: str
    options: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", _freeze(self.options))


@dataclass(frozen=True)
class FileAccessPlan(AccessPlan):
    """Access plan for a downloadable file, optionally contained in an archive."""

    archive: Optional[str] = None
    kind: str = field(default="file", init=False)


@dataclass(frozen=True)
class RemoteDatasetPlan(AccessPlan):
    """Access plan for a remotely readable dataset such as a COG."""

    kind: str = field(default="remote-dataset", init=False)


@dataclass(frozen=True)
class ServiceQueryPlan(AccessPlan):
    """Access plan for a queryable service endpoint."""

    kind: str = field(default="service-query", init=False)


@dataclass(frozen=True)
class Resource:
    """A uniquely selected, metadata-preserving data resource.

    A Resource contains the URI, normalized representation, provenance, and
    explicit access plan selected by the Resolver. Use :meth:`open` with a
    named execution runtime, or pass it to ``Rhinestone.open``.
    """

    uri: str
    format: Optional[str]
    media_type: Optional[str]
    metadata: Metadata
    provenance: Provenance
    access_plan: AccessPlan
    source: Source
    local_path: Optional[str] = None
    _opener: Optional[Callable[[LibraryName], object]] = field(
        default=None, repr=False, compare=False
    )
    discovery: Optional[DiscoveryRecord] = None

    @overload
    def open(self, library: Literal["rasterio"]) -> _RasterioDatasetReader: ...

    @overload
    def open(self, library: Literal["gdal"]) -> _GdalDataset: ...

    @overload
    def open(self, library: Literal["pyogrio"]) -> _GeoDataFrame: ...

    @overload
    def open(self, library: Literal["json-service"]) -> object: ...

    @overload
    def open(self, library: str) -> object: ...

    def open(self, library: LibraryName) -> object:
        """Open this resource through the explicitly selected runtime.

        Args:
            library: Registered execution adapter name, such as ``"gdal"``,
                ``"rasterio"``, ``"pyogrio"``, or ``"json-service"``.

        Raises:
            ExecutionAdapterUnavailableError: If the resource is detached, the
                adapter is unavailable, or no compatible runtime was injected.
            ResourceAccessError: If the selected runtime cannot open the data.
        """
        if self._opener is None:
            raise ExecutionAdapterUnavailableError(
                "Resource is not bound to an execution context; use "
                "app.resolve(config_or_result) before calling Resource.open"
            )
        return self._opener(library)


@dataclass(frozen=True)
class SearchQuery:
    """Immutable search criteria projected to each source's capabilities.

    ``bbox`` is ``(west, south, east, north)``. ``time`` is a ``(start, end)``
    pair where either endpoint may be ``None``. Unsupported supplied criteria
    are reported through ``SearchResults.diagnostics``.
    """

    text: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    time: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None
    limit: Optional[int] = None

    def __post_init__(self) -> None:
        raw_text = cast(object, self.text)
        if raw_text is not None and not isinstance(raw_text, str):
            raise ConfigValidationError(
                "text must be a string or None (SearchQuery.text); "
                f"got {type(raw_text).__name__}"
            )
        if self.limit is not None and (type(self.limit) is not int or self.limit < 0):
            raise ConfigValidationError(
                "limit must be a non-negative integer (SearchQuery.limit); "
                f"got {type(self.limit).__name__}"
            )
        raw_bbox = cast(object, self.bbox)
        if raw_bbox is not None:
            if not isinstance(raw_bbox, tuple):
                raise ConfigValidationError(
                    "bbox must be a tuple of four numbers (SearchQuery.bbox); "
                    f"got {type(raw_bbox).__name__}"
                )
            bbox_values = cast(Tuple[Any, ...], raw_bbox)
            if len(bbox_values) != 4 or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in bbox_values
            ):
                raise ConfigValidationError(
                    "bbox must be a tuple of four numbers (SearchQuery.bbox); "
                    "got a tuple with an invalid length or element type"
                )
        raw_time = cast(object, self.time)
        if raw_time is not None:
            if not isinstance(raw_time, tuple):
                raise ConfigValidationError(
                    "time must be a tuple of two datetime or None values "
                    "(SearchQuery.time); "
                    f"values; got {type(raw_time).__name__}"
                )
            time_values = cast(Tuple[Any, ...], raw_time)
            if len(time_values) != 2 or any(
                value is not None and not isinstance(value, datetime)
                for value in time_values
            ):
                raise ConfigValidationError(
                    "time must be a tuple of two datetime or None values "
                    "(SearchQuery.time); "
                    "got a tuple with an invalid length or element type"
                )

    @property
    def supplied_conditions(self) -> FrozenSet[str]:
        """Return the names of criteria explicitly supplied by the caller."""

        return frozenset(
            name
            for name in ("text", "bbox", "time", "limit")
            if getattr(self, name) is not None
        )

    def project(self, supported_conditions: Iterable[str]) -> "SearchQuery":
        """Return a query containing only source-supported criteria."""
        supported = frozenset(supported_conditions)
        return SearchQuery(
            text=self.text if "text" in supported else None,
            bbox=self.bbox if "bbox" in supported else None,
            time=self.time if "time" in supported else None,
            limit=self.limit if "limit" in supported else None,
        )


@dataclass(frozen=True)
class SearchDiagnostic:
    """Explain how one source participated in a federated search.

    ``reason`` is normally ``unsupported``, ``missing_required``, or
    ``provider_failure``. For provider failures, ``failure_type`` distinguishes
    metadata retrieval from response interpretation without exposing raw
    exceptions in search results.
    """

    source_id: str
    skipped_conditions: FrozenSet[str]
    reason: str = "unsupported"
    missing_conditions: FrozenSet[str] = frozenset()
    failure_type: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ConfigValidationError(
                "search diagnostic source_id must be non-empty; identify the "
                "source that produced the diagnostic"
            )
        object.__setattr__(
            self, "skipped_conditions", frozenset(self.skipped_conditions)
        )
        object.__setattr__(
            self, "missing_conditions", frozenset(self.missing_conditions)
        )


@dataclass(frozen=True)
class Result:
    """A searchable dataset result that can be resolved into a Resource.

    The result preserves display metadata and provenance from discovery. Its
    ``target`` is the configuration used by the normal resolution pipeline.
    """

    title: str
    description: Optional[str]
    discovered_by: str
    target: Config
    metadata: Metadata
    provenance: Provenance
    _resolver: Optional[Callable[[], Resource]] = field(
        default=None, repr=False, compare=False
    )
    raw_metadata: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.discovered_by:
            raise ConfigValidationError(
                "Result.discovered_by must be a non-empty string; identify the "
                "source that discovered this result"
            )
        object.__setattr__(self, "raw_metadata", _freeze(self.raw_metadata))

    def to_config(self) -> Config:
        """Return the immutable target configuration for resolution."""
        return self.target

    def resolve(self) -> Resource:
        """Resolve this result in the application that returned it.

        Raises:
            ConfigValidationError: If this detached result is not bound to an
                application context.
        """
        if self._resolver is None:
            raise ConfigValidationError(
                "Result is not bound to a Rhinestone application; use "
                "app.resolve(result) with the application that produced it"
            )
        return self._resolver()


# Advanced implementation code may use this descriptive alias.
SearchResult = Result


__all__ = [
    "AccessPlan",
    "Config",
    "Dependencies",
    "DiscoveryRecord",
    "DependencyValue",
    "FileAccessPlan",
    "LibraryName",
    "Metadata",
    "Provenance",
    "Provider",
    "RemoteDatasetPlan",
    "Resource",
    "ResourceCandidate",
    "Result",
    "Runtime",
    "RuntimeFactory",
    "SearchDiagnostic",
    "SearchQuery",
    "SearchResult",
    "ServiceQueryPlan",
    "Source",
    "SourceDefinition",
]
