"""Domain models, including the small public vocabulary."""

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    FrozenSet,
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

LibraryName = Literal["gdal", "json-service", "pyogrio", "rasterio"]
"""Execution runtime names accepted by the public open API."""

DependencyValue = Union[object, Callable[[], Any]]
"""An injected runtime object or a lazy factory returning one."""

Runtime = DependencyValue
"""A runtime object or a lazy factory returning one."""
"""An injected runtime object or a lazy factory returning one."""


class _RasterioDatasetReader(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class _GdalDataset(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class _GeoDataFrame(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class Dependencies(TypedDict, total=False):
    """IDE-discoverable names for supported external runtime dependencies."""

    gdal: DependencyValue
    """GDAL Python bindings used for raster, vector, and tile access."""

    rasterio: DependencyValue
    """Rasterio used for COG and GeoTIFF access."""

    pyogrio: DependencyValue
    """Pyogrio used for vector data access."""

    rdflib: DependencyValue
    """RDFLib used for DCAT catalog interpretation."""


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

    @property
    def supplied_conditions(self) -> FrozenSet[str]:
        return frozenset(
            name
            for name in ("text", "bbox", "time", "limit")
            if getattr(self, name) is not None
        )


@dataclass(frozen=True)
class Result:
    title: str
    description: Optional[str]
    source_id: str
    settings: Mapping[str, Any]
    metadata: Metadata
    provenance: Provenance
    _resolver: Optional[Callable[[], Resource]] = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _freeze(self.settings))

    def to_config(self) -> Config:
        return Config(source_id=self.source_id, settings=self.settings)

    def resolve(self) -> Resource:
        """Resolve this result in the Rhinestone application that returned it."""
        if self._resolver is None:
            raise ConfigValidationError(
                "Result is not bound to a Rhinestone application"
            )
        return self._resolver()
\n\n# Advanced code may still use the descriptive internal spelling.\nSearchResult = Result\n

# Advanced implementation code may use this descriptive alias.
SearchResult = Result
