"""Domain models, including the small public vocabulary."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import isfinite
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import (
    Any,
    Literal,
    Protocol,
    TypedDict,
    cast,
    overload,
)

from ._uri import is_valid_http_authority
from .errors import ConfigValidationError, ExecutionAdapterUnavailableError
from .representations.types import Format, FormatPreset, expand_formats

LibraryName = str
"""Execution runtime name accepted by the public open API."""


class ProviderId(str, Enum):
    """Typed IDs for the built-in Providers; custom Providers use their own IDs."""

    GEOSPATIAL_JP = "geospatial-jp"
    PLATEAU = "plateau"
    GSI = "gsi"
    ODPT = "odpt"
    MLIT_DPF = "mlit-dpf"
    SEARCH_CKAN_JP = "search-ckan-jp"


@dataclass(frozen=True)
class RuntimeFactory:
    """Describe a runtime factory evaluated only when its runtime is needed.

    The zero-argument callable is not evaluated during application
    configuration. Its result is cached within the configured dependency
    scope.
    """

    factory: Callable[[], Any]


DependencyValue = object | RuntimeFactory
"""An injected Source Runtime object or an explicit lazy RuntimeFactory."""

Runtime = DependencyValue
"""A Runtime object or an explicit lazy RuntimeFactory."""


class _RasterioDatasetReader(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class _GdalDataset(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class _GeoDataFrame(Protocol):
    def __getattr__(self, name: str) -> Any: ...


class Dependencies(TypedDict, total=False):
    """IDE-discoverable names for Source runtimes."""

    rdflib: DependencyValue
    """Source Runtime used when searching or resolving a DCAT catalog."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return MappingProxyType({key: _freeze(item) for key, item in mapping.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in cast(list[Any], value))
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in cast(tuple[Any, ...], value))
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in cast(set[Any], value))
    return value


def _empty_mapping() -> Mapping[str, Any]:
    return {}


@dataclass(frozen=True)
class Provider:
    """Describe one configured data provider.

    ``id`` is the application-local identifier used by ``Reference`` and search
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


@dataclass(frozen=True)
class Reference:
    """Identify one delivery target within a configured Provider.

    Dataset and resource identifiers are separate so catalogs that expose
    several distributions never collapse those distributions into one result.
    ``parameters`` contains only non-secret provider-specific identifiers that
    are needed to load the target directly.
    """

    provider_id: str
    dataset_identifier: str | None = None
    resource_identifier: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        raw_provider_id = cast(object, self.provider_id)
        if not isinstance(raw_provider_id, str) or not raw_provider_id.strip():
            raise ConfigValidationError(
                "Reference.provider_id must be a non-empty configured Provider ID"
            )
        for name in ("dataset_identifier", "resource_identifier"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ConfigValidationError(
                    f"Reference.{name} must be a non-empty string or None"
                )
        raw_parameters = cast(object, self.parameters)
        if not isinstance(raw_parameters, Mapping):
            raise ConfigValidationError("Reference.parameters must be a mapping")
        _validate_plan_value(self.parameters, "Reference.parameters")
        object.__setattr__(self, "parameters", _freeze(self.parameters))


@dataclass(frozen=True)
class Metadata:
    """Normalized human-readable metadata retained from a source response.

    Common fields support display and inspection while provider-specific values
    remain available in the immutable ``raw`` mapping.
    """

    title: str | None = None
    description: str | None = None
    publisher: str | None = None
    license: str | None = None
    updated_at: datetime | None = None
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
    dataset_identifier: str | None = None
    resource_identifier: str | None = None
    api_endpoint: str | None = None
    original_url: str | None = None
    query_parameters: Mapping[str, Any] = field(default_factory=_empty_mapping)
    retrieved_at: datetime | None = None
    checksum: str | None = None
    adapter: str | None = None
    adapter_version: str | None = None
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
        """Return the source id using the discovery terminology."""
        return self.source_id


_SECRET_OPTION_KEYS = frozenset(
    {"apikey", "authorization", "consumerkey", "password", "secret", "token"}
)


def _validate_plan_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        if not isfinite(value):
            raise ConfigValidationError(f"{path} must contain finite JSON numbers")
        return
    if isinstance(value, Mapping):
        for key, item in cast(Mapping[Any, Any], value).items():
            if not isinstance(key, str):
                raise ConfigValidationError(f"{path} must contain only string keys")
            normalized = key.casefold().replace("_", "").replace("-", "")
            normalized = normalized.rsplit(":", 1)[-1]
            if normalized in _SECRET_OPTION_KEYS:
                raise ConfigValidationError(
                    f"{path}.{key} must not contain a credential value; use "
                    "AccessPlan.credential as a logical reference"
                )
            _validate_plan_value(item, f"{path}.{key}")
        return
    if isinstance(value, tuple | list):
        for index, item in enumerate(cast(tuple[Any, ...] | list[Any], value)):
            _validate_plan_value(item, f"{path}[{index}]")
        return
    raise ConfigValidationError(
        f"{path} contains non-JSON value {type(value).__name__}"
    )


@dataclass(frozen=True)
class AccessPlan:
    """Portable instructions describing how a selected resource is delivered.

    The plan is a standalone, versioned JSON contract. It contains only
    representation metadata, logical identifiers, and JSON-safe execution
    options; runtime objects and credential values never belong here.
    """

    kind: str
    uri: str
    format: str | None = None
    media_type: str | None = None
    options: Mapping[str, Any] = field(default_factory=_empty_mapping)
    provider: str | None = None
    service: str | None = None
    credential: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"file", "remote-dataset", "service-query"}:
            raise ConfigValidationError(
                "AccessPlan.kind must be 'file', 'remote-dataset', or 'service-query'"
            )
        raw_uri = cast(object, self.uri)
        if not isinstance(raw_uri, str) or not raw_uri.strip():
            raise ConfigValidationError("AccessPlan.uri must be a non-empty string")
        if not is_valid_http_authority(self.uri):
            raise ConfigValidationError(
                "AccessPlan.uri must not contain embedded credentials or an "
                "invalid HTTP(S) authority"
            )
        for name in ("format", "media_type", "provider", "service", "credential"):
            value = cast(object, getattr(self, name))
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ConfigValidationError(
                    f"AccessPlan.{name} must be a non-empty string or None"
                )
        raw_options = cast(object, self.options)
        if not isinstance(raw_options, Mapping):
            raise ConfigValidationError("AccessPlan.options must be a mapping")
        _validate_plan_value(self.options, "AccessPlan.options")
        archive = self.options.get("archive")
        if archive not in (None, "zip"):
            raise ConfigValidationError("AccessPlan.options.archive must be 'zip'")
        entry_point = self.options.get("entry_point")
        if entry_point is not None:
            if archive != "zip" or not isinstance(entry_point, str):
                raise ConfigValidationError(
                    "AccessPlan.options.entry_point requires archive='zip' and "
                    "a string path"
                )
            path = PurePosixPath(entry_point)
            if (
                not entry_point.strip()
                or not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in entry_point
            ):
                raise ConfigValidationError(
                    "AccessPlan.options.entry_point must be a safe relative "
                    "archive path"
                )
        encoding = self.options.get("encoding")
        if encoding is not None and (
            not isinstance(encoding, str) or not encoding.strip()
        ):
            raise ConfigValidationError(
                "AccessPlan.options.encoding must be a non-empty string"
            )
        object.__setattr__(self, "options", _freeze(self.options))

    def to_dict(self) -> dict[str, Any]:
        """Return the versioned JSON representation of this plan."""
        from ._portable import access_plan_to_dict

        return access_plan_to_dict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AccessPlan:
        """Validate and restore a plan from its JSON representation."""
        from ._portable import access_plan_from_dict

        return access_plan_from_dict(value)


@dataclass(frozen=True)
class Resource:
    """A uniquely selected, metadata-preserving data resource.

    A Resource contains the URI, normalized representation, provenance, and
    explicit access plan selected by its Provider. Use :meth:`open` with a
    named adapter and an explicit runtime, or pass it to ``Rhinestone.open``.
    """

    uri: str
    format: str | None
    media_type: str | None
    metadata: Metadata
    provenance: Provenance
    access_plan: AccessPlan | None
    reference: Reference
    local_path: str | None = None
    _opener: Callable[[Resource, LibraryName, object | None], object] | None = field(
        default=None, repr=False, compare=False
    )
    discovery: DiscoveryRecord | None = None

    def __post_init__(self) -> None:
        raw_uri = cast(object, self.uri)
        if not isinstance(raw_uri, str) or not raw_uri.strip():
            raise ConfigValidationError("Resource.uri must be a non-empty string")
        if not is_valid_http_authority(self.uri):
            raise ConfigValidationError(
                "Resource.uri must not contain embedded credentials or an "
                "invalid HTTP(S) authority"
            )
        for name in ("format", "media_type", "local_path"):
            value = cast(object, getattr(self, name))
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ConfigValidationError(
                    f"Resource.{name} must be a non-empty string or None"
                )
        if self.access_plan is None:
            return
        if self.uri != self.access_plan.uri:
            raise ConfigValidationError(
                "Resource.uri must equal Resource.access_plan.uri"
            )
        if self.format != self.access_plan.format:
            raise ConfigValidationError(
                "Resource.format must equal Resource.access_plan.format"
            )
        if self.media_type != self.access_plan.media_type:
            raise ConfigValidationError(
                "Resource.media_type must equal Resource.access_plan.media_type"
            )

    @property
    def title(self) -> str:
        """Return a stable display title for search result rendering."""
        return self.metadata.title or self.reference.resource_identifier or self.uri

    @property
    def description(self) -> str | None:
        """Return the normalized discovery description."""
        return self.metadata.description

    @property
    def discovered_by(self) -> str:
        """Return the Provider that discovered this delivery target."""
        return (
            self.discovery.source_id
            if self.discovery is not None
            else self.reference.provider_id
        )

    @property
    def formats(self) -> frozenset[str]:
        """Return this single delivery's normalized format, when known."""
        return frozenset() if self.format is None else frozenset({self.format})

    @overload
    def open(
        self, library: Literal["rasterio"], *, runtime: object
    ) -> _RasterioDatasetReader: ...

    @overload
    def open(self, library: Literal["gdal"], *, runtime: object) -> _GdalDataset: ...

    @overload
    def open(
        self, library: Literal["pyogrio"], *, runtime: object
    ) -> _GeoDataFrame: ...

    @overload
    def open(
        self, library: Literal["json-service"], *, runtime: object | None = None
    ) -> object: ...

    @overload
    def open(self, library: str, *, runtime: object | None = None) -> object: ...

    def open(self, library: LibraryName, *, runtime: object | None = None) -> object:
        """Open this resource through the explicitly selected runtime.

        Args:
            library: Registered execution adapter name, such as ``"gdal"``,
                ``"rasterio"``, ``"pyogrio"``, or ``"json-service"``.
            runtime: User-owned runtime object required by external adapters.
                The core-owned ``json-service`` adapter supplies its own runtime.

        Raises:
            ExecutionAdapterUnavailableError: If the resource is detached, the
                adapter is unavailable, or no compatible runtime was injected.
            ResourceAccessError: If the selected runtime cannot open the data.
        """
        if self._opener is None:
            raise ExecutionAdapterUnavailableError(
                "Resource is not bound to an execution context; use "
                "app.bind(resource) before calling Resource.open"
            )
        return self._opener(self, library, runtime)

    def to_dict(self) -> dict[str, Any]:
        """Return a versioned JSON-safe representation without runtime state."""
        from ._portable import resource_to_dict

        return resource_to_dict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Resource:
        """Restore a detached Resource from :meth:`to_dict` output."""
        from ._portable import resource_from_dict

        return resource_from_dict(value)


@dataclass(frozen=True)
class SearchQuery:
    """Immutable search criteria projected to each source's capabilities.

    ``area`` is an administrative-area name, alias, or code resolved before
    provider dispatch. ``bbox`` remains ``(west, south, east, north)`` and is
    mutually exclusive with ``area``. ``time`` is a ``(start, end)`` pair where
    either endpoint may be ``None``. Unsupported supplied criteria
    are reported through ``SearchResults.diagnostics``.
    """

    text: str | None = None
    area: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    time: tuple[datetime | None, datetime | None] | None = None
    format: tuple[Format | FormatPreset, ...] | None = None
    limit: int | None = None
    providers: Sequence[ProviderId | str] | None = None

    def __post_init__(self) -> None:
        raw_providers = cast(object, self.providers)
        if raw_providers is not None:
            if isinstance(raw_providers, str) or not isinstance(
                raw_providers, Sequence
            ):
                raise ConfigValidationError(
                    "providers must be an array of ProviderId or non-empty ID strings"
                )
            values = cast(Sequence[Any], raw_providers)
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ConfigValidationError(
                    "providers must be an array of ProviderId or non-empty ID strings"
                )
            object.__setattr__(self, "providers", tuple(values))
        raw_text = cast(object, self.text)
        if raw_text is not None and not isinstance(raw_text, str):
            raise ConfigValidationError(
                "text must be a string or None (SearchQuery.text); "
                f"got {type(raw_text).__name__}"
            )
        raw_area = cast(object, self.area)
        if raw_area is not None and (
            not isinstance(raw_area, str) or not raw_area.strip()
        ):
            raise ConfigValidationError(
                "area must be a non-empty string or None (SearchQuery.area)"
            )
        if self.area is not None and self.bbox is not None:
            raise ConfigValidationError(
                "area and bbox cannot be supplied together; choose a named area "
                "or an explicit bounding box"
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
            bbox_values = cast(tuple[Any, ...], raw_bbox)
            if len(bbox_values) != 4 or any(
                isinstance(value, bool) or not isinstance(value, int | float)
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
            time_values = cast(tuple[Any, ...], raw_time)
            if len(time_values) != 2 or any(
                value is not None and not isinstance(value, datetime)
                for value in time_values
            ):
                raise ConfigValidationError(
                    "time must be a tuple of two datetime or None values "
                    "(SearchQuery.time); "
                    "got a tuple with an invalid length or element type"
                )
        raw_format = cast(object, self.format)
        if raw_format is not None:
            format_values = (
                cast(tuple[Any, ...], raw_format)
                if isinstance(raw_format, tuple)
                else ()
            )
            if not format_values or any(
                not isinstance(value, Format | FormatPreset) for value in format_values
            ):
                raise ConfigValidationError(
                    "format must be a non-empty tuple of Format or FormatPreset values "
                    "(SearchQuery.format)"
                )

    @property
    def supplied_conditions(self) -> frozenset[str]:
        """Return the names of criteria explicitly supplied by the caller."""

        return frozenset(
            name
            for name in ("text", "area", "bbox", "time", "format", "limit")
            if getattr(self, name) is not None
        )

    def project(self, supported_conditions: Iterable[str]) -> SearchQuery:
        """Return a query containing only source-supported criteria."""
        supported = frozenset(supported_conditions)
        return SearchQuery(
            text=self.text if "text" in supported else None,
            area=self.area if "area" in supported else None,
            bbox=self.bbox if "bbox" in supported else None,
            time=self.time if "time" in supported else None,
            format=self.format if "format" in supported else None,
            limit=self.limit if "limit" in supported else None,
        )

    @property
    def expanded_formats(self) -> frozenset[Format]:
        """Return concrete canonical formats with presets expanded."""
        return expand_formats(self.format or ())

    @property
    def text_terms(self) -> tuple[str, ...]:
        """Return non-empty whitespace-delimited terms in ``text``.

        Local catalog adapters use these terms with AND semantics.  Remote
        adapters receive ``text`` verbatim because their server-side query
        language remains provider-defined.
        """

        return () if self.text is None else tuple(self.text.split())


@dataclass(frozen=True)
class SearchDiagnostic:
    """Explain how one source participated in a federated search.

    ``reason`` is normally ``unsupported``, ``missing_required``,
    ``area_resolution_failed``, ``provider_failure``, or ``item_skipped``.
    For provider failures, ``failure_type`` distinguishes metadata retrieval,
    response interpretation, and unavailable credentials without exposing raw
    exceptions in search results. Item-scoped diagnostics identify the skipped
    provider resource and expose a stable machine-readable ``detail``.
    """

    source_id: str
    skipped_conditions: frozenset[str]
    reason: str = "unsupported"
    missing_conditions: frozenset[str] = frozenset()
    failure_type: str | None = None
    resource_identifier: str | None = None
    detail: str | None = None

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
class SearchExecution:
    """One provider search execution measured by the coordinator.

    ``elapsed_ms`` covers the adapter call only.  It is intended for comparing
    configured providers in tests or application telemetry, not for ranking
    results across providers.
    """

    source_id: str
    elapsed_ms: float
    result_count: int

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ConfigValidationError("search execution source_id must be non-empty")
        raw_elapsed_ms = cast(object, self.elapsed_ms)
        if (
            isinstance(raw_elapsed_ms, bool)
            or not isinstance(raw_elapsed_ms, int | float)
            or not isfinite(raw_elapsed_ms)
            or raw_elapsed_ms < 0
        ):
            raise ConfigValidationError(
                "search execution elapsed_ms must be a finite non-negative number"
            )
        if type(self.result_count) is not int or self.result_count < 0:
            raise ConfigValidationError(
                "search execution result_count must be a non-negative integer"
            )


@dataclass(frozen=True)
class ProviderSearchResults(Sequence[Resource]):
    """Carry provider results and item-scoped diagnostics atomically."""

    results: tuple[Resource, ...]
    diagnostics: tuple[SearchDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "results", tuple(self.results))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def __iter__(self) -> Iterator[Resource]:
        return iter(self.results)

    @overload
    def __getitem__(self, index: int) -> Resource: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Resource, ...]: ...

    def __getitem__(self, index: int | slice) -> Resource | tuple[Resource, ...]:
        return self.results[index]

    def __len__(self) -> int:
        return len(self.results)


__all__ = [
    "AccessPlan",
    "Dependencies",
    "DiscoveryRecord",
    "DependencyValue",
    "LibraryName",
    "Metadata",
    "Provenance",
    "Provider",
    "ProviderId",
    "ProviderSearchResults",
    "Reference",
    "Resource",
    "Runtime",
    "RuntimeFactory",
    "SearchDiagnostic",
    "SearchExecution",
    "SearchQuery",
]
