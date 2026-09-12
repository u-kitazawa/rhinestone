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

from .errors import ConfigValidationError, ExecutionAdapterUnavailableError

LibraryName = str
"""Execution runtime name accepted by the public open API."""


@dataclass(frozen=True)
class RuntimeFactory:
    """An explicit lazy factory for a user-owned Runtime."""

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


@dataclass(frozen=True)
class Provider:
    """A data provider selected from a catalog."""

    id: str
    adapter_type: str
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ConfigValidationError("source id must be a non-empty string")
        if not self.adapter_type:
            raise ConfigValidationError("adapter_type must be a non-empty string")
        object.__setattr__(self, "settings", _freeze(self.settings))


# Advanced implementation code may use this descriptive alias.
SourceDefinition = Provider


@dataclass(frozen=True)
class Config:
    source_id: str
    settings: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ConfigValidationError("source_id must be a non-empty string")
        object.__setattr__(self, "settings", _freeze(self.settings))


@dataclass(frozen=True)
class Metadata:
    title: Optional[str] = None
    description: Optional[str] = None
    publisher: Optional[str] = None
    license: Optional[str] = None
    updated_at: Optional[datetime] = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw", _freeze(self.raw))


@dataclass(frozen=True)
class Provenance:
    provider: str
    dataset_identifier: Optional[str] = None
    resource_identifier: Optional[str] = None
    api_endpoint: Optional[str] = None
    original_url: Optional[str] = None
    query_parameters: Mapping[str, Any] = field(default_factory=dict)
    retrieved_at: Optional[datetime] = None
    checksum: Optional[str] = None
    adapter: Optional[str] = None
    adapter_version: Optional[str] = None
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_parameters", _freeze(self.query_parameters))
        object.__setattr__(self, "raw", _freeze(self.raw))


@dataclass(frozen=True)
class ResourceCandidate:
    uri: str
    format: Optional[str]
    media_type: Optional[str]
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze(self.attributes))


@dataclass(frozen=True)
class Source:
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
    kind: str
    uri: str
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", _freeze(self.options))


@dataclass(frozen=True)
class FileAccessPlan(AccessPlan):
    archive: Optional[str] = None
    kind: str = field(default="file", init=False)


@dataclass(frozen=True)
class RemoteDatasetPlan(AccessPlan):
    kind: str = field(default="remote-dataset", init=False)


@dataclass(frozen=True)
class ServiceQueryPlan(AccessPlan):
    kind: str = field(default="service-query", init=False)


@dataclass(frozen=True)
class Resource:
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
        """Open this Resource through the explicitly selected runtime library."""
        if self._opener is None:
            raise ExecutionAdapterUnavailableError(
                "Resource is not bound to an execution context"
            )
        return self._opener(library)


@dataclass(frozen=True)
class SearchQuery:
    text: Optional[str] = None
    bbox: Optional[Tuple[float, float, float, float]] = None
    time: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None
    limit: Optional[int] = None

    def __post_init__(self) -> None:
        raw_text = cast(object, self.text)
        if raw_text is not None and not isinstance(raw_text, str):
            raise ConfigValidationError("text must be a string or None")
        if self.limit is not None and (type(self.limit) is not int or self.limit < 0):
            raise ConfigValidationError(
                "limit must be a non-negative integer (SearchQuery.limit); "
                f"got {type(self.limit).__name__}"
            )
        raw_bbox = cast(object, self.bbox)
        if raw_bbox is not None:
            if not isinstance(raw_bbox, tuple):
                raise ConfigValidationError("bbox must be a tuple of four numbers")
            bbox_values = cast(Tuple[Any, ...], raw_bbox)
            if len(bbox_values) != 4 or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in bbox_values
            ):
                raise ConfigValidationError("bbox must be a tuple of four numbers")
        raw_time = cast(object, self.time)
        if raw_time is not None:
            if not isinstance(raw_time, tuple):
                raise ConfigValidationError(
                    "time must be a tuple of two datetime or None values"
                )
            time_values = cast(Tuple[Any, ...], raw_time)
            if len(time_values) != 2 or any(
                value is not None and not isinstance(value, datetime)
                for value in time_values
            ):
                raise ConfigValidationError(
                    "time must be a tuple of two datetime or None values"
                )

    @property
    def supplied_conditions(self) -> FrozenSet[str]:
        return frozenset(
            name
            for name in ("text", "bbox", "time", "limit")
            if getattr(self, name) is not None
        )

    def project(self, supported_conditions: Iterable[str]) -> "SearchQuery":
        """Return the portion of this query understood by a source."""
        supported = frozenset(supported_conditions)
        return SearchQuery(
            text=self.text if "text" in supported else None,
            bbox=self.bbox if "bbox" in supported else None,
            time=self.time if "time" in supported else None,
            limit=self.limit if "limit" in supported else None,
        )


@dataclass(frozen=True)
class SearchDiagnostic:
    """Explain how one source participated in a search."""

    source_id: str
    skipped_conditions: FrozenSet[str]
    reason: str = "unsupported"
    missing_conditions: FrozenSet[str] = frozenset()
    failure_type: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ConfigValidationError("search diagnostic source_id must be non-empty")
        object.__setattr__(
            self, "skipped_conditions", frozenset(self.skipped_conditions)
        )
        object.__setattr__(
            self, "missing_conditions", frozenset(self.missing_conditions)
        )


@dataclass(frozen=True)
class Result:
    title: str
    description: Optional[str]
    discovered_by: str
    target: Config
    metadata: Metadata
    provenance: Provenance
    _resolver: Optional[Callable[[], Resource]] = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not self.discovered_by:
            raise ConfigValidationError("discovered_by must be a non-empty string")

    def to_config(self) -> Config:
        """Return the target configuration for the normal resolve pipeline."""
        return self.target

    def resolve(self) -> Resource:
        """Resolve this result in the Rhinestone application that returned it."""
        if self._resolver is None:
            raise ConfigValidationError(
                "Result is not bound to a Rhinestone application"
            )
        return self._resolver()


# Advanced implementation code may use this descriptive alias.
SearchResult = Result
