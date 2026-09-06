"""Source adapter for repository-managed static service definitions."""

from typing import Any, Dict, List, Mapping, Optional, Tuple, cast

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
from .._knowledge import string
from ..base import ProviderAdapter


class StaticAdapter(ProviderAdapter):
    """Resolve immutable, repository-managed source definitions."""

    adapter_type = "static"
    search_conditions = frozenset({"text", "limit"})

    def __init__(self, items: Mapping[str, Mapping[str, Any]]) -> None:
        super().__init__(get_json=lambda url, params: None)
        self._items = self._validate_items(items)

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        identifier = string(settings, "id")
        try:
            item = self._items[identifier]
        except KeyError:
            raise ResourceNotFoundError(
                f"Static source item {identifier!r} does not exist"
            ) from None
        return self._source(identifier, item)

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError(
                "Unsupported static source search condition"
            )
        if query.limit is not None and (
            type(query.limit) is not int or query.limit < 0
        ):
            raise ConfigValidationError("limit must be a non-negative integer")

        results: List[SearchResult] = []
        for identifier in sorted(self._items):
            source = self.load(Config(self.adapter_type, {"id": identifier}))
            title = source.metadata.title or identifier
            description = source.metadata.description
            haystack = " ".join(
                value
                for value in (identifier, title, description)
                if isinstance(value, str)
            )
            if query.text and query.text.casefold() not in haystack.casefold():
                continue
            results.append(
                SearchResult(
                    title,
                    description,
                    self.adapter_type,
                    {"id": identifier},
                    source.metadata,
                    source.provenance,
                )
            )
        return tuple(results[: query.limit])

    @classmethod
    def _validate_items(
        cls, items: Mapping[str, Mapping[str, Any]]
    ) -> Dict[str, Mapping[str, Any]]:
        if not isinstance(items, Mapping) or not items:
            raise ConfigValidationError(
                "static source items must be a non-empty object"
            )

        validated: Dict[str, Mapping[str, Any]] = {}
        for identifier, item in items.items():
            if not isinstance(identifier, str) or not identifier.strip():
                raise ConfigValidationError(
                    "static source item ids must be non-empty strings"
                )
            if not isinstance(item, Mapping):
                raise ConfigValidationError(
                    f"static source item {identifier!r} must be an object"
                )

            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise ConfigValidationError(
                    f"static source item {identifier!r} metadata must be an object"
                )
            candidates = item.get("candidates")
            if not isinstance(candidates, (list, tuple)) or not candidates:
                raise ConfigValidationError(
                    f"static source item {identifier!r} must define candidates"
                )
            for candidate in candidates:
                cls._validate_candidate(identifier, candidate)

            capabilities = item.get("capabilities", ())
            if not isinstance(capabilities, (list, tuple)):
                raise ConfigValidationError(
                    f"static source item {identifier!r} capabilities must be an array"
                )
            if any(
                not isinstance(capability, str) or not capability.strip()
                for capability in capabilities
            ):
                raise ConfigValidationError(
                    f"static source item {identifier!r} capabilities must be strings"
                )

            provenance = item.get("provenance", {})
            if not isinstance(provenance, Mapping):
                raise ConfigValidationError(
                    f"static source item {identifier!r} provenance must be an object"
                )
            validated[identifier] = item
        return validated

    @staticmethod
    def _validate_candidate(identifier: str, candidate: Any) -> None:
        if not isinstance(candidate, Mapping):
            raise ConfigValidationError(
                f"static source item {identifier!r} candidate must be an object"
            )
        candidate_values = cast(Mapping[str, Any], candidate)
        uri = candidate_values.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            raise ConfigValidationError(
                f"static source item {identifier!r} candidate uri must be non-empty"
            )
        for field in ("format", "media_type"):
            value = candidate_values.get(field)
            if value is not None and not isinstance(value, str):
                raise ConfigValidationError(
                    f"static source item {identifier!r} candidate {field} must be a string"
                )
        attributes = candidate_values.get("attributes", {})
        if not isinstance(attributes, Mapping):
            raise ConfigValidationError(
                f"static source item {identifier!r} candidate attributes must be an object"
            )

    def _source(self, identifier: str, item: Mapping[str, Any]) -> Source:
        metadata_values = cast(Mapping[str, Any], item.get("metadata", {}))
        metadata_raw = metadata_values.get("raw", metadata_values)
        if not isinstance(metadata_raw, Mapping):
            raise ConfigValidationError(
                f"static source item {identifier!r} metadata.raw must be an object"
            )

        candidates: List[ResourceCandidate] = []
        for candidate_value in item["candidates"]:
            candidate = cast(Mapping[str, Any], candidate_value)
            candidates.append(
                ResourceCandidate(
                    uri=cast(str, candidate["uri"]),
                    format=_optional_string(candidate.get("format")),
                    media_type=_optional_string(candidate.get("media_type")),
                    attributes=cast(Mapping[str, Any], candidate.get("attributes", {})),
                )
            )

        capabilities = frozenset(
            cast(Tuple[str, ...], tuple(item.get("capabilities", ())))
        )
        provenance_values = cast(Mapping[str, Any], item.get("provenance", {}))
        query_parameters = cast(
            Mapping[str, Any], provenance_values.get("query_parameters", {})
        )
        if not isinstance(query_parameters, Mapping):
            raise ConfigValidationError(
                f"static source item {identifier!r} provenance.query_parameters must be an object"
            )

        raw_item = item
        provenance = Provenance(
            provider=self.adapter_type,
            dataset_identifier=_optional_string(
                provenance_values.get("dataset_identifier")
            )
            or identifier,
            resource_identifier=_optional_string(
                provenance_values.get("resource_identifier")
            ),
            api_endpoint=_optional_string(provenance_values.get("api_endpoint")),
            original_url=_optional_string(provenance_values.get("original_url")),
            query_parameters=query_parameters,
            adapter=self.adapter_type,
            raw=raw_item,
        )
        return Source(
            metadata=Metadata(
                title=_optional_string(metadata_values.get("title")) or identifier,
                description=_optional_string(metadata_values.get("description")),
                publisher=_optional_string(metadata_values.get("publisher")),
                license=_optional_string(metadata_values.get("license")),
                raw=metadata_raw,
            ),
            candidates=tuple(candidates),
            capabilities=capabilities,
            provenance=provenance,
            raw_metadata=raw_item,
        )


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
