"""STAC API 1.0 source adapter."""

from typing import Any, Dict, List, Optional, Sequence, Tuple

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
from ..base import JsonObject, JsonTransport, ProviderAdapter


class StacAdapter(ProviderAdapter):
    adapter_type = "stac"
    search_conditions = frozenset({"bbox", "time", "limit"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = None,
        api_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
    ) -> None:
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            api_token=api_token,
            api_key=api_key,
            api_key_header=api_key_header,
        )

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        endpoint = self._endpoint_from(settings)
        collection_id = self._required_string(settings, "collection_id")
        item_id = self._required_string(settings, "item_id")
        asset_key = self._required_string(settings, "asset_key")
        item_url = f"{endpoint}/collections/{collection_id}/items/{item_id}"
        item = self._request(item_url, {})
        asset = self._asset(item, asset_key)
        candidate = self._candidate(asset, asset_key)
        properties = self._object(item.get("properties"), "STAC properties")
        metadata = Metadata(
            title=_optional_string(properties.get("title")) or item_id,
            description=_optional_string(properties.get("description")),
            raw=item,
        )
        provenance = Provenance(
            provider="stac",
            dataset_identifier=collection_id,
            resource_identifier=item_id,
            api_endpoint=endpoint,
            original_url=candidate.uri,
            query_parameters={"asset_key": asset_key},
            adapter="stac",
            raw=item,
        )
        return Source(
            metadata=metadata,
            candidates=(candidate,),
            capabilities=frozenset({"download", "search"}),
            provenance=provenance,
            raw_metadata=item,
        )

    def search(
        self, query: SearchQuery, collections: Sequence[str] = ()
    ) -> Tuple[SearchResult, ...]:
        endpoint = self._endpoint_from({}, self._endpoint)
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported STAC search conditions: {', '.join(sorted(unsupported))}"
            )
        params = self._query_parameters(query)
        if collections:
            params["collections"] = ",".join(collections)
        response = self._request(f"{endpoint}/search", params)
        items = self._objects(response.get("features"), "STAC features")
        found: List[SearchResult] = []
        for item in items:
            item_id = self._required_string(item, "id")
            collection_id = self._required_string(item, "collection")
            properties = self._object(item.get("properties"), "STAC properties")
            asset_key = self._single_data_asset_key(item)
            title = _optional_string(properties.get("title")) or item_id
            found.append(
                SearchResult(
                    title=title,
                    description=_optional_string(properties.get("description")),
                    source_id=self.adapter_type,
                    provider_settings={
                        "endpoint": endpoint,
                        "collection_id": collection_id,
                        "item_id": item_id,
                        "asset_key": asset_key,
                    },
                    metadata=Metadata(title=title, raw=item),
                    provenance=Provenance(
                        provider="stac",
                        dataset_identifier=collection_id,
                        resource_identifier=item_id,
                        api_endpoint=endpoint,
                        query_parameters=params,
                        adapter="stac",
                        raw=item,
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

    def _asset(self, item: JsonObject, key: str) -> JsonObject:
        assets = self._object(item.get("assets"), "STAC assets")
        if key not in assets:
            raise ProviderResponseError(f"Requested STAC asset {key!r} is missing")
        return self._object(assets[key], f"STAC asset {key!r}")

    def _candidate(self, asset: JsonObject, key: str) -> ResourceCandidate:
        uri = self._required_string(asset, "href")
        media_type = _optional_string(asset.get("type"))
        format_name = "cog" if media_type and "cloud-optimized" in media_type else None
        return ResourceCandidate(
            uri=uri,
            format=format_name,
            media_type=media_type,
            attributes={"asset_key": key, "asset": asset},
        )

    def _single_data_asset_key(self, item: JsonObject) -> str:
        assets = self._object(item.get("assets"), "STAC assets")
        data_keys: List[str] = []
        for key, raw_asset in assets.items():
            asset = self._object(raw_asset, f"STAC asset {key!r}")
            roles = asset.get("roles", [])
            if isinstance(roles, list) and "data" in roles:
                data_keys.append(key)
        if len(data_keys) != 1:
            raise ProviderResponseError(
                "STAC search result must expose exactly one data asset"
            )
        return data_keys[0]


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
