"""OGC API Features 1.0 source adapter."""

from typing import Any, Dict, List, Mapping, Optional, Tuple

from ....errors import ConfigValidationError, ProviderResponseError
from ....models import (
    Config,
    Metadata,
    Provenance,
    ResourceCandidate,
    SearchQuery,
    SearchResult,
    Source,
)
from ....registry import CredentialRegistry
from ....security import DestinationPolicy
from ..base import JsonObject, JsonTransport, ProviderAdapter


class OgcFeaturesAdapter(ProviderAdapter):
    adapter_type = "ogc-features"
    search_conditions = frozenset({"bbox", "time", "limit"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = None,
        collection_id: Optional[str] = None,
        api_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        credential: Optional[str] = None,
        credential_header: Optional[str] = None,
        credential_scheme: Optional[str] = None,
        credentials: Optional[CredentialRegistry] = None,
        destination_policy: Optional[DestinationPolicy] = None,
    ) -> None:
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            api_token=api_token,
            api_key=api_key,
            api_key_header=api_key_header,
            credential=credential,
            credential_header=credential_header,
            credential_scheme=credential_scheme,
            credentials=credentials,
            destination_policy=destination_policy,
        )
        self._collection_id = collection_id

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        endpoint = self._endpoint_from(settings)
        collection_id = self._required_string(settings, "collection_id")
        collection_url = f"{endpoint}/collections/{collection_id}"
        collection = self._request(collection_url, {})
        items_link = self._items_link(collection)
        feature_id = settings.get("feature_id")
        uri = items_link["href"]
        if isinstance(feature_id, str) and feature_id:
            uri = f"{uri.rstrip('/')}/{feature_id}"
        candidate = ResourceCandidate(
            uri=uri,
            format="ogc-api-features",
            media_type=_optional_string(items_link.get("type")),
            attributes={"collection_id": collection_id, "feature_id": feature_id},
        )
        provenance = Provenance(
            provider="ogc-features",
            dataset_identifier=collection_id,
            resource_identifier=feature_id if isinstance(feature_id, str) else None,
            api_endpoint=endpoint,
            original_url=uri,
            adapter="ogc-features",
            raw=collection,
        )
        return Source(
            metadata=Metadata(
                title=_optional_string(collection.get("title")) or collection_id,
                description=_optional_string(collection.get("description")),
                raw=collection,
            ),
            candidates=(candidate,),
            capabilities=frozenset({"service-query", "search"}),
            provenance=provenance,
            raw_metadata=collection,
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        endpoint = self._endpoint_from({}, self._endpoint)
        if not self._collection_id:
            raise ConfigValidationError("collection_id is required for OGC search")
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported OGC search conditions: {', '.join(sorted(unsupported))}"
            )
        params = self._query_parameters(query)
        items_url = f"{endpoint}/collections/{self._collection_id}/items"
        response = self._request(items_url, params)
        features = self._objects(response.get("features"), "OGC features")
        found: List[SearchResult] = []
        for feature in features:
            feature_id = self._required_string(feature, "id")
            properties = self._object(feature.get("properties"), "OGC properties")
            title = _feature_title(properties, feature_id)
            found.append(
                SearchResult(
                    title=title,
                    description=_optional_string(properties.get("description")),
                    discovered_by=self.adapter_type,
                    target=Config(
                        self.adapter_type,
                        {
                            "collection_id": self._collection_id,
                            "feature_id": feature_id,
                        },
                    ),
                    metadata=Metadata(title=title, raw=feature),
                    provenance=Provenance(
                        provider="ogc-features",
                        dataset_identifier=self._collection_id,
                        resource_identifier=feature_id,
                        api_endpoint=endpoint,
                        query_parameters=params,
                        adapter="ogc-features",
                        raw=feature,
                    ),
                )
            )
        return tuple(found)

    @staticmethod
    def _query_parameters(query: SearchQuery) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
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


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
