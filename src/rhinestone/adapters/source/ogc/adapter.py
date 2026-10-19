"""OGC API Features 1.0 source adapter."""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import ConfigValidationError, ProviderResponseError
from ....models import (
    Metadata,
    Provenance,
    ProviderSearchResults,
    Reference,
    Resource,
    SearchDiagnostic,
    SearchQuery,
)
from ....registry import CredentialRegistry
from ....resolution import resource_from_delivery
from ....security import DestinationPolicy
from .._uri import append_path_segment, resolve_response_href
from ..base import JsonObject, JsonTransport, ProviderAdapter


class OgcFeaturesAdapter(ProviderAdapter):
    """Interpret OGC API Features collections and item services."""

    adapter_type = "ogc-features"
    search_conditions = frozenset({"bbox", "time", "limit"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: str | None = None,
        collection_id: str | None = None,
        credential: str | None = None,
        credential_header: str | None = None,
        credential_scheme: str | None = None,
        credentials: CredentialRegistry | None = None,
        destination_policy: DestinationPolicy | None = None,
        provider_id: str | None = None,
    ) -> None:
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            credential=credential,
            credential_header=credential_header,
            credential_scheme=credential_scheme,
            credentials=credentials,
            destination_policy=destination_policy,
            provider_id=provider_id,
        )
        self._collection_id = collection_id

    def load(self, reference: Reference) -> Resource:
        """Load one OGC collection and its explicit items endpoint."""
        settings = self._reference_parameters(
            reference, dataset_key="collection_id", resource_key="feature_id"
        )
        endpoint = self._endpoint_from(settings)
        collection_id = self._required_string(settings, "collection_id")
        collection_path = self._encode_path_segment(collection_id)
        collection_url = f"{endpoint}/collections/{collection_path}"
        collection, response_uri = self._request_with_uri(collection_url, {})
        items_link = self._items_link(collection)
        feature_id = settings.get("feature_id")
        uri = resolve_response_href(response_uri, items_link["href"])
        if isinstance(feature_id, str) and feature_id:
            uri = append_path_segment(uri, feature_id)
        provenance = Provenance(
            provider="ogc-features",
            dataset_identifier=collection_id,
            resource_identifier=feature_id if isinstance(feature_id, str) else None,
            api_endpoint=endpoint,
            original_url=uri,
            adapter="ogc-features",
            raw=collection,
        )
        return resource_from_delivery(
            reference=Reference(
                reference.provider_id,
                dataset_identifier=collection_id,
                resource_identifier=feature_id
                if isinstance(feature_id, str)
                else collection_id,
                parameters=reference.parameters,
            ),
            uri=uri,
            format="ogc-api-features",
            media_type=_optional_string(items_link.get("type")),
            metadata=Metadata(
                title=_optional_string(collection.get("title")) or collection_id,
                description=_optional_string(collection.get("description")),
                raw=collection,
            ),
            provenance=provenance,
            kind="service-query",
            options={"collection_id": collection_id, "feature_id": feature_id},
        )

    def search(self, query: SearchQuery) -> ProviderSearchResults:
        """Search one configured OGC collection using standard parameters."""
        endpoint = self._endpoint_from({}, self._endpoint)
        if not self._collection_id:
            raise ConfigValidationError("collection_id is required for OGC search")
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported OGC search conditions: {', '.join(sorted(unsupported))}"
            )
        params = self._query_parameters(query)
        collection_path = self._encode_path_segment(self._collection_id)
        items_url = f"{endpoint}/collections/{collection_path}/items"
        response = self._request(items_url, params)
        raw_features = response.get("features")
        features = (
            cast(list[Any], raw_features)
            if isinstance(raw_features, list)
            else self._objects(raw_features, "OGC features")
        )
        found: list[Resource] = []
        diagnostics: list[SearchDiagnostic] = []
        for raw_feature in features:
            feature_id = None
            try:
                feature = self._object(raw_feature, "OGC feature")
                feature_id = _optional_string(feature.get("id"))
                if feature_id is not None and not feature_id.strip():
                    feature_id = None
                if not feature_id:
                    raise ProviderResponseError(
                        "OGC feature id must be a non-empty string"
                    )
                properties = self._object(feature.get("properties"), "OGC properties")
                title = _feature_title(properties, feature_id)
                uri = append_path_segment(items_url, feature_id)
                provenance = Provenance(
                    provider="ogc-features",
                    dataset_identifier=self._collection_id,
                    resource_identifier=feature_id,
                    api_endpoint=endpoint,
                    original_url=uri,
                    query_parameters=params,
                    adapter="ogc-features",
                    raw=feature,
                )
                found.append(
                    resource_from_delivery(
                        reference=Reference(
                            self.adapter_type,
                            dataset_identifier=self._collection_id,
                            resource_identifier=feature_id,
                            parameters={
                                "collection_id": self._collection_id,
                                "feature_id": feature_id,
                            },
                        ),
                        uri=uri,
                        format="ogc-api-features",
                        media_type="application/geo+json",
                        metadata=Metadata(
                            title=title,
                            description=_optional_string(properties.get("description")),
                            raw=feature,
                        ),
                        provenance=provenance,
                        kind="service-query",
                        options={"query": params},
                    )
                )
            except ProviderResponseError:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=self.adapter_type,
                        skipped_conditions=frozenset(),
                        reason="item_skipped",
                        resource_identifier=feature_id,
                        detail="invalid_feature",
                    )
                )
        return ProviderSearchResults(tuple(found), tuple(diagnostics))

    @staticmethod
    def _query_parameters(query: SearchQuery) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if query.bbox is not None:
            params["bbox"] = ",".join(str(value) for value in query.bbox)
        if query.time is not None:
            start, end = query.time
            params["datetime"] = "/".join(
                value.isoformat() if value is not None else ".."
                for value in (start, end)
            )
        if query.limit is not None:
            params["limit"] = query.limit
        return params

    def _items_link(self, collection: JsonObject) -> JsonObject:
        links = self._objects(collection.get("links"), "OGC links")
        for link in links:
            if link.get("rel") == "items" and isinstance(link.get("href"), str):
                return link
        raise ProviderResponseError("OGC collection has no items link")


def _feature_title(properties: Mapping[str, Any], fallback: str) -> str:
    for key in ("title", "name"):
        value = properties.get(key)
        if isinstance(value, str):
            return value
    return fallback


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
