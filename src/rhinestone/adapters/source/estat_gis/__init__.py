"""Declarative e-Stat Statistics GIS distribution adapter.

The current e-Stat public workflow exposes boundary downloads through the
Statistics GIS download UI.  Since that UI is not a stable machine API, this
adapter accepts an explicit, application-owned distribution index.  It keeps
provider discovery separate from general GIS resource access and never scrapes
HTML or guesses a download URL.
"""

import json
from copy import deepcopy
from importlib import resources
from types import MappingProxyType
from typing import Any, Iterable, List, Mapping, Optional, Tuple, cast
from urllib.parse import urlparse

from ...._uri import is_valid_http_authority
from ....errors import (
    ConfigValidationError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from ....models import (
    Config,
    Metadata,
    Provenance,
    ResourceCandidate,
    SearchQuery,
    SearchResult,
    Source,
)
from ....representations import CANONICAL_FORMATS, canonical_format
from ...knowledge import KnowledgeAdapterRegistry
from .._knowledge import entry_point, resolve_knowledge
from ..base import ProviderAdapter

_FORMATS = frozenset({"shapefile", "gml", "kml"}) & CANONICAL_FORMATS
_SELECTORS = frozenset(
    {
        "distribution_id",
        "dataset_id",
        "boundary_kind",
        "survey_year",
        "time",
        "time_kind",
        "level",
        "region_code",
        "format",
    }
)


def _thaw_copy(value: Any) -> Any:
    """Copy frozen provider settings into adapter-owned containers."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return {key: _thaw_copy(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        items = cast(Iterable[Any], value)
        return tuple(_thaw_copy(item) for item in items)
    if isinstance(value, list):
        items = cast(Iterable[Any], value)
        return [_thaw_copy(item) for item in items]
    if isinstance(value, frozenset):
        items = cast(Iterable[Any], value)
        return frozenset(_thaw_copy(item) for item in items)
    if isinstance(value, set):
        items = cast(Iterable[Any], value)
        return {_thaw_copy(item) for item in items}
    return deepcopy(value)


class EstatGisAdapter(ProviderAdapter):
    """Resolve explicit e-Stat GIS distributions to ordinary GIS Resources."""

    adapter_type = "estat-gis"
    search_conditions = frozenset({"text", "limit"})

    def config_schema(self) -> Optional[Mapping[str, Any]]:
        """Load the schema beside this package's adapter implementation.

        The implementation remains re-exported from ``__init__`` for the
        built-in public import path, so the base class cannot infer the
        package from ``type(self).__module__`` on its own.
        """
        text = (
            resources.files(cast(str, __package__)).joinpath("schema.json").read_text()
        )
        return cast(Mapping[str, Any], json.loads(text))

    def __init__(
        self,
        distributions: Iterable[Mapping[str, Any]],
        knowledge: Optional[KnowledgeAdapterRegistry] = None,
    ) -> None:
        super().__init__(get_json=lambda url, params: None)
        self._knowledge = knowledge or KnowledgeAdapterRegistry()
        self._raw_distributions, self._distributions = self._validate_distributions(
            distributions
        )
        self._raw_by_distribution_id = MappingProxyType(
            {
                cast(str, item["distribution_id"]): item
                for item in self._raw_distributions
            }
        )

    def load(self, config: Config) -> Source:
        """Resolve one distribution using explicit selectors only."""
        settings = dict(self._config_settings(config))
        unknown = set(settings) - _SELECTORS
        if unknown:
            raise ConfigValidationError(
                "Unknown estat-gis selector(s): " + ", ".join(sorted(unknown))
            )
        if "time_kind" in settings and "time" not in settings:
            raise ConfigValidationError("time_kind requires an explicit time selector")
        if "format" in settings:
            settings["format"] = canonical_format(settings["format"])
        knowledge = resolve_knowledge(settings, self._knowledge)
        self._validate_time_semantic(settings, knowledge)
        matches = tuple(
            item
            for item in self._distributions
            if self._matches(item, settings, knowledge)
        )
        if not matches:
            raise ResourceNotFoundError(
                "No e-Stat GIS distribution matches the explicit selectors"
            )
        candidates = tuple(self._candidate(item, knowledge) for item in matches)
        first = matches[0]
        raw_first = self._raw_distribution(first)
        raw = {"distribution_index": self._raw_distributions}
        return Source(
            metadata=Metadata(
                title=cast(str, first["title"]),
                description=cast(Optional[str], first.get("description")),
                publisher="e-Stat Statistics GIS",
                raw=raw,
            ),
            candidates=candidates,
            capabilities=frozenset({"download"}),
            provenance=Provenance(
                provider=self.adapter_type,
                dataset_identifier=cast(str, first["dataset_id"]),
                resource_identifier=(
                    cast(str, first["distribution_id"]) if len(matches) == 1 else None
                ),
                query_parameters=dict(settings),
                adapter=self.adapter_type,
                raw={"distribution": raw_first, "knowledge": knowledge},
            ),
            raw_metadata=raw,
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        """Search the supplied distribution index, without broadening selectors."""
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError(
                "e-Stat GIS search supports only text and limit"
            )
        results: List[SearchResult] = []
        needle = query.text.casefold() if query.text else None
        for item in self._distributions:
            if query.limit is not None and len(results) >= query.limit:
                break
            haystack = " ".join(
                cast(str, item[field])
                for field in ("distribution_id", "title", "dataset_id", "level")
                if isinstance(item.get(field), str)
            ).casefold()
            if needle and needle not in haystack:
                continue
            distribution_id = cast(str, item["distribution_id"])
            raw_item = self._raw_distribution(item)
            results.append(
                SearchResult(
                    title=cast(str, item["title"]),
                    description=cast(Optional[str], item.get("description")),
                    discovered_by=self.adapter_type,
                    target=Config(
                        self.adapter_type, {"distribution_id": distribution_id}
                    ),
                    metadata=Metadata(
                        title=cast(str, item["title"]),
                        description=cast(Optional[str], item.get("description")),
                        publisher="e-Stat Statistics GIS",
                        raw=raw_item,
                    ),
                    provenance=Provenance(
                        provider=self.adapter_type,
                        dataset_identifier=cast(str, item["dataset_id"]),
                        resource_identifier=distribution_id,
                        adapter=self.adapter_type,
                        raw=raw_item,
                    ),
                    raw_metadata=raw_item,
                )
            )
        return tuple(results[: query.limit])

    def _candidate(
        self, item: Mapping[str, Any], knowledge: Mapping[str, Mapping[str, object]]
    ) -> ResourceCandidate:
        archive = item.get("archive")
        candidate_settings: dict[str, Any] = {}
        if archive is not None:
            candidate_settings["entry_point"] = entry_point(
                {"archive": archive, "entry_point": item.get("entry_point")}
            )
        attributes = {
            "access_kind": "file",
            "archive": archive,
            "access_options": candidate_settings,
            "knowledge": knowledge,
            "dataset_identity": {
                "dataset_id": item["dataset_id"],
                "boundary_kind": item["boundary_kind"],
                "survey_year": item["survey_year"],
                "level": item["level"],
            },
        }
        return ResourceCandidate(
            uri=cast(str, item["uri"]),
            format=cast(str, item["format"]),
            media_type=cast(Optional[str], item.get("media_type")),
            attributes=attributes,
        )

    def _raw_distribution(self, item: Mapping[str, Any]) -> Mapping[str, Any]:
        distribution_id = cast(str, item["distribution_id"])
        return self._raw_by_distribution_id[distribution_id]

    @staticmethod
    def _matches(
        item: Mapping[str, Any],
        settings: Mapping[str, Any],
        knowledge: Mapping[str, Mapping[str, object]],
    ) -> bool:
        for field in (
            "distribution_id",
            "dataset_id",
            "boundary_kind",
            "level",
            "region_code",
            "format",
        ):
            if field in settings and settings[field] != item.get(field):
                return False
        if "survey_year" in settings and settings["survey_year"] != item["survey_year"]:
            return False
        if "time" in settings:
            time = knowledge.get("time", {})
            if time.get("year") != item["survey_year"]:
                return False
        return True

    @staticmethod
    def _validate_time_semantic(
        settings: Mapping[str, Any], knowledge: Mapping[str, Mapping[str, object]]
    ) -> None:
        if "time" in settings and knowledge.get("time", {}).get("kind") != (
            "survey_year"
        ):
            raise ConfigValidationError(
                "e-Stat GIS time selector must be a survey_year"
            )

    @classmethod
    def _validate_distributions(
        cls, distributions: Iterable[Mapping[str, Any]]
    ) -> Tuple[Tuple[Mapping[str, Any], ...], Tuple[Mapping[str, Any], ...]]:
        try:
            values = tuple(distributions)
        except TypeError:
            raise ConfigValidationError(
                "estat-gis distributions must be an array"
            ) from None
        if not values:
            raise ConfigValidationError("estat-gis distributions must not be empty")
        identifiers: set[str] = set()
        raw_result: List[Mapping[str, Any]] = []
        result: List[Mapping[str, Any]] = []
        for raw in values:
            if not isinstance(cast(object, raw), Mapping):
                raise ConfigValidationError(
                    "each estat-gis distribution must be an object"
                )
            item = cast(dict[str, Any], _thaw_copy(raw))
            raw_result.append(cast(Mapping[str, Any], _thaw_copy(item)))
            for field in (
                "distribution_id",
                "dataset_id",
                "boundary_kind",
                "level",
                "uri",
            ):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ConfigValidationError(f"estat-gis {field} must be non-empty")
            if cast(str, item["distribution_id"]) in identifiers:
                raise ConfigValidationError("estat-gis distribution IDs must be unique")
            identifiers.add(cast(str, item["distribution_id"]))
            year = item.get("survey_year")
            if type(year) is not int or not 1 <= year <= 9999:
                raise ConfigValidationError("estat-gis survey_year must be 1..9999")
            if "region_code" in item and (
                not isinstance(item["region_code"], str)
                or not item["region_code"].strip()
            ):
                raise ConfigValidationError(
                    "estat-gis region_code must be a non-empty string"
                )
            format_name = canonical_format(item.get("format"))
            if format_name not in _FORMATS:
                raise ConfigValidationError(
                    "estat-gis format must be shapefile, gml, or kml"
                )
            item["format"] = format_name
            title = item.get("title", item["distribution_id"])
            if not isinstance(title, str) or not title.strip():
                raise ConfigValidationError("estat-gis title must be non-empty")
            item["title"] = title
            if (
                "description" in item
                and item["description"] is not None
                and not isinstance(item["description"], str)
            ):
                raise ConfigValidationError(
                    "estat-gis description must be a string when present"
                )
            uri = cast(str, item["uri"])
            try:
                parsed_uri = urlparse(uri)
                parsed_uri.port
                valid_uri = (
                    parsed_uri.scheme.casefold() == "https"
                    and is_valid_http_authority(uri)
                    and not parsed_uri.query
                    and not parsed_uri.fragment
                )
            except ValueError:
                valid_uri = False
            if not valid_uri:
                raise ConfigValidationError("estat-gis distribution uri must use HTTPS")
            if (
                "media_type" in item
                and item["media_type"] is not None
                and not isinstance(item["media_type"], str)
            ):
                raise ConfigValidationError("estat-gis media_type must be a string")
            if "archive" in item and item["archive"] not in (None, "zip"):
                raise ConfigValidationError(
                    "estat-gis archive must be zip when present"
                )
            media_type = item.get("media_type")
            base_media_type = (
                media_type.split(";", 1)[0].strip().casefold()
                if isinstance(media_type, str)
                else None
            )
            if base_media_type == "application/zip" and item.get("archive") != "zip":
                raise ConfigValidationError(
                    "estat-gis application/zip distributions require archive=zip"
                )
            if "entry_point" in item and item.get("archive") != "zip":
                raise ConfigValidationError(
                    "estat-gis entry_point requires archive=zip"
                )
            if item.get("archive") == "zip":
                entry_point(item)
            result.append(item)
        return tuple(raw_result), tuple(result)


__all__ = ["EstatGisAdapter"]
