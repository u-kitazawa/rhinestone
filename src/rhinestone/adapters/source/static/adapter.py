"""Source adapter for repository-managed static service definitions."""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from ....models import (
    Metadata,
    Provenance,
    Reference,
    Resource,
    SearchQuery,
)
from ....resolution import resource_from_delivery
from .._knowledge import string
from ..base import ProviderAdapter


class StaticAdapter(ProviderAdapter):
    """Resolve immutable, repository-managed source definitions."""

    adapter_type = "static"
    search_conditions = frozenset({"text", "limit"})

    def __init__(self, items: Mapping[str, Mapping[str, Any]]) -> None:
        super().__init__(get_json=lambda url, params: None)
        self._resource_definitions = self._validate_items(items)

    def load(self, reference: Reference) -> Resource:
        """Resolve one repository-managed item by its explicit identifier."""
        settings = self._reference_parameters(reference, dataset_key="id")
        identifier = string(settings, "id")
        try:
            item = self._resource_definitions[identifier]
        except KeyError:
            raise ResourceNotFoundError(
                f"Static source item {identifier!r} does not exist"
            ) from None
        resources = self._build_resources(identifier, item)
        selected = reference.resource_identifier
        if selected is not None:
            matches = tuple(
                resource
                for resource in resources
                if resource.reference.resource_identifier == selected
            )
            if not matches:
                raise ResourceNotFoundError(
                    f"Static item {identifier!r} has no distribution {selected!r}"
                )
            return matches[0]
        if len(resources) != 1:
            raise AmbiguousResourceError(
                f"Static item {identifier!r} has {len(resources)} distributions; "
                "set Reference.resource_identifier"
            )
        return resources[0]

    def search(self, query: SearchQuery) -> tuple[Resource, ...]:
        """Search static item identifiers and metadata by text and limit."""
        if query.supplied_conditions - self.search_conditions:
            raise UnsupportedSearchConditionError(
                "Unsupported static source search condition"
            )

        results: list[Resource] = []
        for identifier in sorted(self._resource_definitions):
            resources = self._build_resources(
                identifier, self._resource_definitions[identifier]
            )
            title = resources[0].metadata.title or identifier
            description = resources[0].metadata.description
            haystack = " ".join(
                value
                for value in (identifier, title, description)
                if isinstance(value, str)
            )
            normalized_haystack = haystack.casefold()
            if any(
                term.casefold() not in normalized_haystack for term in query.text_terms
            ):
                continue
            results.extend(resources)
            if query.limit is not None and len(results) >= query.limit:
                return tuple(results[: query.limit])
        return tuple(results[: query.limit])

    @classmethod
    def _validate_items(cls, items: Any) -> dict[str, Mapping[str, Any]]:
        if not isinstance(items, Mapping) or not items:
            raise ConfigValidationError(
                "static source items must be a non-empty object"
            )

        item_values = cast(Mapping[Any, Any], items)
        validated: dict[str, Mapping[str, Any]] = {}
        for raw_identifier, raw_item in item_values.items():
            if not isinstance(raw_identifier, str) or not raw_identifier.strip():
                raise ConfigValidationError(
                    "static source item ids must be non-empty strings"
                )
            if not isinstance(raw_item, Mapping):
                raise ConfigValidationError(
                    f"static source item {raw_identifier!r} must be an object"
                )
            identifier = raw_identifier
            item = cast(Mapping[str, Any], raw_item)

            metadata = item.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise ConfigValidationError(
                    f"static source item {identifier!r} metadata must be an object"
                )
            candidates_value = item.get("candidates")
            if not isinstance(candidates_value, list | tuple) or not candidates_value:
                raise ConfigValidationError(
                    f"static source item {identifier!r} must define candidates"
                )
            for candidate in cast(Any, candidates_value):
                cls._validate_candidate(identifier, candidate)

            capabilities_value = item.get("capabilities", ())
            if not isinstance(capabilities_value, list | tuple):
                raise ConfigValidationError(
                    f"static source item {identifier!r} capabilities must be an array"
                )
            if any(
                not isinstance(capability, str) or not capability.strip()
                for capability in cast(Any, capabilities_value)
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

    def _build_resources(
        self, identifier: str, item: Mapping[str, Any]
    ) -> tuple[Resource, ...]:
        metadata_values = cast(Mapping[str, Any], item.get("metadata", {}))
        metadata_raw_value: Any = metadata_values.get("raw", metadata_values)
        if not isinstance(metadata_raw_value, Mapping):
            raise ConfigValidationError(
                f"static source item {identifier!r} metadata.raw must be an object"
            )
        metadata_raw = cast(Mapping[str, Any], metadata_raw_value)

        provenance_values = cast(Mapping[str, Any], item.get("provenance", {}))
        query_parameters_value: Any = provenance_values.get("query_parameters", {})
        if not isinstance(query_parameters_value, Mapping):
            raise ConfigValidationError(
                f"static source item {identifier!r} provenance.query_parameters must be an object"
            )
        query_parameters = cast(Mapping[str, Any], query_parameters_value)

        raw_item: Mapping[str, Any] = item
        dataset_identifier = (
            _optional_string(provenance_values.get("dataset_identifier")) or identifier
        )
        metadata = Metadata(
            title=_optional_string(metadata_values.get("title")) or identifier,
            description=_optional_string(metadata_values.get("description")),
            publisher=_optional_string(metadata_values.get("publisher")),
            license=_optional_string(metadata_values.get("license")),
            raw=metadata_raw,
        )
        resources: list[Resource] = []
        for index, candidate_value in enumerate(item["candidates"]):
            candidate = cast(Mapping[str, Any], candidate_value)
            attributes = cast(Mapping[str, Any], candidate.get("attributes", {}))
            explicit_identifier = _optional_string(
                provenance_values.get("resource_identifier")
            )
            resource_identifier = explicit_identifier or str(index)
            uri = cast(str, candidate["uri"])
            provenance = Provenance(
                provider=self.adapter_type,
                dataset_identifier=dataset_identifier,
                resource_identifier=resource_identifier,
                api_endpoint=_optional_string(provenance_values.get("api_endpoint")),
                original_url=uri,
                query_parameters=query_parameters,
                adapter=self.adapter_type,
                raw=raw_item,
            )
            access_options = attributes.get("access_options", {})
            if not isinstance(access_options, Mapping):
                raise ConfigValidationError("static access_options must be an object")
            options = dict(cast(Mapping[str, Any], access_options))
            service = options.pop("service", None)
            credential = options.pop("credential", None)
            resources.append(
                resource_from_delivery(
                    reference=Reference(
                        self.adapter_type,
                        dataset_identifier=dataset_identifier,
                        resource_identifier=resource_identifier,
                        parameters={"id": identifier},
                    ),
                    uri=uri,
                    format=_optional_string(candidate.get("format")),
                    media_type=_optional_string(candidate.get("media_type")),
                    metadata=metadata,
                    provenance=provenance,
                    kind=_optional_string(attributes.get("access_kind")),
                    options=options,
                    encoding=_optional_string(attributes.get("encoding")),
                    archive=_optional_string(attributes.get("archive")),
                    service=service if isinstance(service, str) else None,
                    credential=credential if isinstance(credential, str) else None,
                )
            )
        return tuple(resources)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
