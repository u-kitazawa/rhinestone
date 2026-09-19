"""Discovery-only adapter for the MLIT Data Platform GraphQL API."""

import json
import math
from collections.abc import Callable, Mapping
from typing import Any, cast
from urllib.parse import urlsplit

from ...._uri import is_valid_http_authority
from ....errors import (
    ConfigValidationError,
    ProviderResponseError,
    UnsupportedSourceError,
)
from ....models import Config, Metadata, Provenance, SearchQuery, SearchResult, Source
from ....registry import CredentialRegistry
from ....representations import canonical_format
from ..base import ProviderAdapter

DEFAULT_ENDPOINT = "https://data-platform.mlit.go.jp/api/v1"
DEFAULT_LIMIT = 50

JsonPoster = Callable[..., Any]
JsonObject = Mapping[str, Any]


class MlitDpfAdapter(ProviderAdapter):
    """Discover DPF records and delegate them to configured source providers."""

    adapter_type = "mlit-dpf"
    search_conditions = frozenset({"text", "bbox", "limit"})
    required_search_conditions: frozenset[str] = frozenset()

    def __init__(
        self,
        post_json: JsonPoster,
        credentials: CredentialRegistry,
        provider_id: str,
        endpoint: str = DEFAULT_ENDPOINT,
        credential: object = "mlit-dpf",
        target_rules: object = (),
        representations: object = None,
    ) -> None:
        super().__init__(get_json=lambda _url, _params: None)
        self._post_json = post_json
        self._credentials = credentials
        self._provider_id = provider_id
        self._endpoint = self._normalize_endpoint(endpoint)
        if not isinstance(credential, str) or not credential:
            raise ConfigValidationError(
                "mlit-dpf credential must be a non-empty logical credential name"
            )
        self._credential = credential
        self._target_rules = _validate_target_rules(target_rules)
        self._representations = _validate_representations(
            {} if representations is None else representations
        )

    def load(self, config: Config) -> Source:
        """Reject resolution because DPF is only a discovery source."""
        raise UnsupportedSourceError(
            "mlit-dpf is a discovery-only source and cannot resolve resources"
        )

    def search(self, query: SearchQuery) -> tuple[SearchResult, ...]:
        """Search DPF, preferring explicit native-source delegation."""
        limit = DEFAULT_LIMIT if query.limit is None else query.limit
        if limit == 0:
            return ()
        graphql = _build_query(query, limit)
        headers = {"apikey": self._credentials.get(self._credential)}
        response = self._post_json(
            self._endpoint,
            {"query": graphql},
            headers,
            credential=self._credential,
        )
        root = _object(response, "MLIT DPF response root")
        errors = root.get("errors")
        if errors:
            raise ProviderResponseError("MLIT DPF GraphQL response contains errors")
        data = _object(root.get("data"), "MLIT DPF data")
        search = _object(data.get("search"), "MLIT DPF search result")
        records = search.get("searchResults")
        if not isinstance(records, list):
            raise ProviderResponseError(
                "MLIT DPF searchResults must be an array; response shape is invalid"
            )
        parameters = _query_parameters(query, limit)
        found: list[SearchResult] = []
        for value in cast(list[Any], records):
            record = _object(value, "MLIT DPF search record")
            found.extend(self._record_results(record, parameters))
        return tuple(found[:limit])

    def _record_results(
        self, record: JsonObject, parameters: Mapping[str, Any]
    ) -> tuple[SearchResult, ...]:
        data_id = _required_record_string(record, "id")
        dataset_id = _required_record_string(record, "dataset_id")
        catalog_id = _required_record_string(record, "catalog_id")
        title = _optional_string(record.get("title")) or data_id
        raw_metadata = record.get("metadata", {})
        if raw_metadata is None:
            raw_metadata = {}
        metadata_values = _object(raw_metadata, "MLIT DPF record metadata")
        metadata = Metadata(title=title, raw=record)
        provenance = Provenance(
            provider=self._provider_id,
            dataset_identifier=dataset_id,
            resource_identifier=data_id,
            api_endpoint=self._endpoint,
            query_parameters=parameters,
            adapter=self.adapter_type,
            raw={
                "catalog_id": catalog_id,
                "dataset_id": dataset_id,
                "data_id": data_id,
                "record": record,
            },
        )
        target = self._native_target(record, metadata_values, catalog_id, dataset_id)
        if target is not None:
            return (
                SearchResult(
                    title=title,
                    description=None,
                    discovered_by=self.adapter_type,
                    target=target,
                    metadata=metadata,
                    provenance=provenance,
                    raw_metadata=record,
                ),
            )
        representation = self._representations.get(dataset_id)
        if representation is None:
            return ()
        urls = metadata_values.get("DPF:downloadURLs")
        if urls is None:
            return ()
        if not isinstance(urls, list) or any(
            not isinstance(url, str) for url in cast(list[Any], urls)
        ):
            raise ProviderResponseError(
                "MLIT DPF DPF:downloadURLs must be an array of URL strings"
            )
        results: list[SearchResult] = []
        for uri in cast(list[str], urls):
            if not is_valid_http_authority(uri) or urlsplit(
                uri
            ).scheme.casefold() not in {"http", "https"}:
                raise ProviderResponseError(
                    "MLIT DPF download URL must be a safe HTTP(S) URL without credentials"
                )
            settings: dict[str, Any] = {
                "uri": uri,
                "format": representation["format"],
                "metadata": {"title": title, "raw": record},
            }
            for name in ("media_type", "archive"):
                if name in representation:
                    settings[name] = representation[name]
            results.append(
                SearchResult(
                    title=title,
                    description=None,
                    discovered_by=self.adapter_type,
                    target=Config("direct", settings),
                    metadata=metadata,
                    provenance=provenance,
                    raw_metadata=record,
                )
            )
        return tuple(results)

    def _native_target(
        self,
        record: JsonObject,
        metadata: JsonObject,
        catalog_id: str,
        dataset_id: str,
    ) -> Config | None:
        for rule in self._target_rules:
            if rule["catalog_id"] != catalog_id:
                continue
            rule_dataset = rule.get("dataset_id")
            if rule_dataset is not None and rule_dataset != dataset_id:
                continue
            settings: dict[str, Any] = {}
            for name, selector in cast(
                Mapping[str, Mapping[str, str]], rule["settings"]
            ).items():
                source_name, key = next(iter(selector.items()))
                source = record if source_name == "record" else metadata
                value = source.get(key)
                if not isinstance(value, str) or not value:
                    break
                settings[name] = value
            else:
                return Config(cast(str, rule["source_id"]), settings)
        return None


def _build_query(query: SearchQuery, limit: int) -> str:
    arguments = ["first: 0", f"size: {limit}"]
    if query.text is not None:
        arguments.append(f"term: {json.dumps(query.text, ensure_ascii=False)}")
        arguments.append("phraseMatch: true")
    if query.bbox is not None:
        west, south, east, north = query.bbox
        if not all(math.isfinite(value) for value in query.bbox):
            raise ConfigValidationError("mlit-dpf bbox coordinates must be finite")
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            raise ConfigValidationError(
                "mlit-dpf bbox must be ordered WGS84 coordinates within valid ranges"
            )
        arguments.append(
            "locationFilter: { rectangle: { "
            f"topLeft: {{ lat: {north}, lon: {west} }}, "
            f"bottomRight: {{ lat: {south}, lon: {east} }} "
            "} }"
        )
    joined = ", ".join(arguments)
    return (
        "query { search(" + joined + ") { totalNumber searchResults { "
        "id title lat lon year theme metadata dataset_id catalog_id } } }"
    )


def _query_parameters(query: SearchQuery, limit: int) -> Mapping[str, Any]:
    parameters: dict[str, Any] = {"limit": limit}
    if query.text is not None:
        parameters["text"] = query.text
    if query.bbox is not None:
        parameters["bbox"] = query.bbox
    return parameters


def _validate_target_rules(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list | tuple):
        raise ConfigValidationError("mlit-dpf target_rules must be an array")
    rules: list[Mapping[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for raw_item in cast(list[Any] | tuple[Any, ...], value):
        if not isinstance(raw_item, Mapping):
            raise ConfigValidationError("each mlit-dpf target rule must be an object")
        item = cast(Mapping[str, Any], raw_item)
        unknown = set(item) - {"catalog_id", "dataset_id", "source_id", "settings"}
        if unknown:
            raise ConfigValidationError(
                "unknown mlit-dpf target rule fields: " + ", ".join(sorted(unknown))
            )
        catalog_id = _configured_string(item, "catalog_id", "target rule")
        source_id = _configured_string(item, "source_id", "target rule")
        dataset_value = item.get("dataset_id")
        if dataset_value is not None and (
            not isinstance(dataset_value, str) or not dataset_value
        ):
            raise ConfigValidationError(
                "mlit-dpf target rule dataset_id must be a non-empty string"
            )
        dataset_id = dataset_value
        key = (catalog_id, dataset_id)
        if key in seen:
            raise ConfigValidationError(
                "mlit-dpf target_rules contain an ambiguous duplicate for "
                f"catalog_id {catalog_id!r} and dataset_id {dataset_id!r}"
            )
        seen.add(key)
        settings = item.get("settings")
        if not isinstance(settings, Mapping) or not settings:
            raise ConfigValidationError(
                "mlit-dpf target rule settings must be a non-empty object"
            )
        normalized: dict[str, Mapping[str, str]] = {}
        typed_settings = cast(Mapping[Any, Any], settings)
        for name, raw_selector in typed_settings.items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(raw_selector, Mapping)
            ):
                raise ConfigValidationError(
                    "mlit-dpf target setting selectors must be named objects"
                )
            selector = cast(Mapping[Any, Any], raw_selector)
            if len(selector) != 1 or next(iter(selector), None) not in {
                "record",
                "metadata",
            }:
                raise ConfigValidationError(
                    "mlit-dpf target setting selector must contain exactly one "
                    "record or metadata key"
                )
            selector_value = next(iter(selector.values()))
            if not isinstance(selector_value, str) or not selector_value:
                raise ConfigValidationError(
                    "mlit-dpf target setting selector value must be a non-empty string"
                )
            normalized[name] = cast(Mapping[str, str], dict(selector))
        rules.append(
            {
                "catalog_id": catalog_id,
                "dataset_id": dataset_id,
                "source_id": source_id,
                "settings": normalized,
            }
        )
    return tuple(sorted(rules, key=lambda rule: rule["dataset_id"] is None))


def _validate_representations(value: object) -> Mapping[str, Mapping[str, str]]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError("mlit-dpf representations must be an object")
    representations: dict[str, Mapping[str, str]] = {}
    typed_value = cast(Mapping[Any, Any], value)
    for dataset_id, raw_representation in typed_value.items():
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ConfigValidationError(
                "mlit-dpf representation dataset ids must be non-empty strings"
            )
        if not isinstance(raw_representation, Mapping):
            raise ConfigValidationError(
                "each mlit-dpf representation must be an object"
            )
        representation = cast(Mapping[str, Any], raw_representation)
        unknown = set(representation) - {"format", "media_type", "archive"}
        if unknown:
            raise ConfigValidationError(
                "unknown mlit-dpf representation fields: " + ", ".join(sorted(unknown))
            )
        format_name = canonical_format(representation.get("format"))
        if format_name is None:
            raise ConfigValidationError(
                "mlit-dpf representation format must be a non-empty string"
            )
        normalized = {"format": format_name}
        for name in ("media_type", "archive"):
            item = representation.get(name)
            if item is not None:
                if not isinstance(item, str) or not item:
                    raise ConfigValidationError(
                        f"mlit-dpf representation {name} must be a non-empty string"
                    )
                normalized[name] = item
        representations[dataset_id] = normalized
    return representations


def _configured_string(value: Mapping[str, Any], name: str, context: str) -> str:
    item = value.get(name)
    if not isinstance(item, str) or not item:
        raise ConfigValidationError(
            f"mlit-dpf {context} {name} must be a non-empty string"
        )
    return item


def _required_record_string(record: JsonObject, name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value:
        raise ProviderResponseError(
            f"MLIT DPF search record {name} must be a non-empty string"
        )
    return value


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _object(value: Any, context: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ProviderResponseError(f"{context} must be an object")
    return cast(JsonObject, value)
