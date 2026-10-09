"""STAC API 1.0 source adapter."""

from collections.abc import Sequence
from typing import Any

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
from ....representations import format_from_media_type
from ....resolution import resource_from_delivery
from ....security import DestinationPolicy
from .._uri import resolve_response_href
from ..base import JsonObject, JsonTransport, ProviderAdapter


class StacAdapter(ProviderAdapter):
    """Interpret STAC API Items, Assets, and standard search responses."""

    adapter_type = "stac"
    search_conditions = frozenset({"bbox", "time", "limit"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: str | None = None,
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

    def load(self, reference: Reference) -> Resource:
        """Load one STAC Item and its explicitly named Asset."""
        parameters = dict(reference.parameters)
        if reference.resource_identifier is not None:
            item_id, separator, asset_key = reference.resource_identifier.partition(":")
            if separator:
                parameters.setdefault("item_id", item_id)
                parameters.setdefault("asset_key", asset_key)
        settings = self._reference_parameters(
            Reference(
                reference.provider_id,
                reference.dataset_identifier,
                reference.resource_identifier,
                parameters,
            ),
            dataset_key="collection_id",
        )
        endpoint = self._endpoint_from(settings)
        collection_id = self._required_string(settings, "collection_id")
        item_id = self._required_string(settings, "item_id")
        asset_key = self._required_string(settings, "asset_key")
        collection_path = self._encode_path_segment(collection_id)
        item_path = self._encode_path_segment(item_id)
        item_url = f"{endpoint}/collections/{collection_path}/items/{item_path}"
        item, response_uri = self._request_with_uri(item_url, {})
        asset = self._asset(item, asset_key)
        uri, format_name, media_type = self._delivery(asset, response_uri)
        properties = self._object(item.get("properties"), "STAC properties")
        metadata = Metadata(
            title=_optional_string(properties.get("title")) or item_id,
            description=_optional_string(properties.get("description")),
            raw=item,
        )
        provenance = Provenance(
            provider="stac",
            dataset_identifier=collection_id,
            resource_identifier=f"{item_id}:{asset_key}",
            api_endpoint=endpoint,
            original_url=uri,
            query_parameters={"asset_key": asset_key},
            adapter="stac",
            raw=item,
        )
        return resource_from_delivery(
            reference=Reference(
                reference.provider_id,
                dataset_identifier=collection_id,
                resource_identifier=f"{item_id}:{asset_key}",
                parameters=reference.parameters,
            ),
            uri=uri,
            format=format_name,
            media_type=media_type,
            metadata=metadata,
            provenance=provenance,
        )

    def search(
        self, query: SearchQuery, collections: Sequence[str] = ()
    ) -> ProviderSearchResults:
        """Search STAC Items using bbox, datetime, limit, and collections."""
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
        found: list[Resource] = []
        diagnostics: list[SearchDiagnostic] = []
        for item in items:
            item_id = self._required_string(item, "id")
            collection_id = self._required_string(item, "collection")
            properties = self._object(item.get("properties"), "STAC properties")
            asset_keys = self._data_asset_keys(item)
            if not asset_keys:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=self.adapter_type,
                        skipped_conditions=frozenset(),
                        reason="item_skipped",
                        resource_identifier=item_id,
                        detail="missing_data_asset",
                    )
                )
                continue
            title = _optional_string(properties.get("title")) or item_id
            for asset_key in asset_keys:
                asset = self._asset(item, asset_key)
                uri, format_name, media_type = self._delivery(
                    asset, f"{endpoint}/search"
                )
                provenance = Provenance(
                    provider="stac",
                    dataset_identifier=collection_id,
                    resource_identifier=f"{item_id}:{asset_key}",
                    api_endpoint=endpoint,
                    original_url=uri,
                    query_parameters=params,
                    adapter="stac",
                    raw=item,
                )
                found.append(
                    resource_from_delivery(
                        reference=Reference(
                            self.adapter_type,
                            dataset_identifier=collection_id,
                            resource_identifier=f"{item_id}:{asset_key}",
                            parameters={
                                "collection_id": collection_id,
                                "item_id": item_id,
                                "asset_key": asset_key,
                            },
                        ),
                        uri=uri,
                        format=format_name,
                        media_type=media_type,
                        metadata=Metadata(
                            title=title,
                            description=_optional_string(properties.get("description")),
                            raw=item,
                        ),
                        provenance=provenance,
                    )
                )
                if query.limit is not None and len(found) >= query.limit:
                    return ProviderSearchResults(tuple(found), tuple(diagnostics))
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

    def _asset(self, item: JsonObject, key: str) -> JsonObject:
        assets = self._object(item.get("assets"), "STAC assets")
        if key not in assets:
            raise ProviderResponseError(f"Requested STAC asset {key!r} is missing")
        return self._object(assets[key], f"STAC asset {key!r}")

    def _delivery(
        self, asset: JsonObject, response_uri: str
    ) -> tuple[str, str | None, str | None]:
        href = self._required_string(asset, "href")
        uri = resolve_response_href(response_uri, href)
        media_type = _optional_string(asset.get("type"))
        format_name = (
            "cog"
            if media_type and "cloud-optimized" in media_type
            else format_from_media_type(media_type)
        )
        return uri, format_name, media_type

    def _data_asset_keys(self, item: JsonObject) -> tuple[str, ...]:
        assets = self._object(item.get("assets"), "STAC assets")
        data_keys: list[str] = []
        for key, raw_asset in assets.items():
            asset = self._object(raw_asset, f"STAC asset {key!r}")
            roles = asset.get("roles", [])
            if isinstance(roles, list) and "data" in roles:
                data_keys.append(key)
        return tuple(sorted(data_keys))


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
