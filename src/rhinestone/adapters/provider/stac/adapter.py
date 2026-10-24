"""STAC API 1.0 and static catalog provider adapter."""

from collections import deque
from collections.abc import Sequence
from datetime import datetime, timezone
from math import isfinite
from typing import Any, cast
from urllib.parse import urlsplit

import pystac

from ...._uri import is_valid_http_authority
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
        catalog_uri: str | None = None,
        max_documents: int = 100,
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
        if catalog_uri is not None and endpoint is not None:
            raise ConfigValidationError(
                "Configure either endpoint or catalog_uri for STAC, not both"
            )
        if catalog_uri is not None:
            if (
                not isinstance(cast(object, catalog_uri), str)
                or not catalog_uri.strip()
                or not catalog_uri.casefold().startswith(("http://", "https://"))
                or not is_valid_http_authority(catalog_uri)
            ):
                raise ConfigValidationError(
                    "catalog_uri must be a valid URI with a valid HTTP(S) authority "
                    "and without embedded credentials"
                )
            self._catalog_uri = catalog_uri
        else:
            self._catalog_uri = None
        if type(max_documents) is not int:
            raise ConfigValidationError("max_documents must be a positive integer")
        if max_documents < 1:
            raise ConfigValidationError("max_documents must be a positive integer")
        self._max_documents = max_documents

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
        collection_id = self._required_string(settings, "collection_id")
        item_id = self._required_string(settings, "item_id")
        asset_key = self._required_string(settings, "asset_key")
        item_href = settings.get("item_href")
        if item_href is not None:
            if self._catalog_uri is None:
                raise ConfigValidationError(
                    "item_href is only supported by a static STAC Provider"
                )
            try:
                item_url = resolve_response_href(
                    self._catalog_uri, cast(str, item_href)
                )
            except ValueError as error:
                raise ConfigValidationError("item_href is invalid") from error
            api_endpoint = self._catalog_uri
        else:
            endpoint = self._endpoint_from(settings)
            collection_path = self._encode_path_segment(collection_id)
            item_path = self._encode_path_segment(item_id)
            item_url = f"{endpoint}/collections/{collection_path}/items/{item_path}"
            api_endpoint = endpoint
        item, response_uri = self._request_with_uri(item_url, {})
        parsed = self._parse_item(item, response_uri)
        asset = self._asset(item, asset_key)
        uri, format_name, media_type = self._delivery(asset, parsed, asset_key)
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
            api_endpoint=api_endpoint,
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
        if self._catalog_uri is not None:
            return self._search_static(query, collections)
        endpoint = self._endpoint_from({}, self._endpoint)
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported STAC search conditions: {', '.join(sorted(unsupported))}"
            )
        if query.limit == 0:
            return ProviderSearchResults((), ())
        params = self._query_parameters(query)
        if collections:
            params["collections"] = ",".join(collections)
        response, response_uri = self._request_with_uri(f"{endpoint}/search", params)
        raw_items = response.get("features")
        if not isinstance(raw_items, list):
            raise ProviderResponseError("STAC features must be an array")
        items = cast(list[Any], raw_items)
        found: list[Resource] = []
        diagnostics: list[SearchDiagnostic] = []
        for raw_item in items:
            item_id = None
            try:
                item = self._object(raw_item, "STAC item")
                item_id = _optional_string(item.get("id"))
                if item_id is not None and not item_id.strip():
                    item_id = None
                item_results = self._item_resources(item, response_uri, params)
            except (ConfigValidationError, ProviderResponseError):
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=self.adapter_type,
                        skipped_conditions=frozenset(),
                        reason="item_skipped",
                        resource_identifier=item_id,
                        detail="invalid_item",
                    )
                )
                continue
            if not item_results:
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
            for result in item_results:
                found.append(result)
                if query.limit is not None and len(found) >= query.limit:
                    return ProviderSearchResults(tuple(found), tuple(diagnostics))
        return ProviderSearchResults(tuple(found), tuple(diagnostics))

    def _search_static(
        self, query: SearchQuery, collections: Sequence[str]
    ) -> ProviderSearchResults:
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported STAC search conditions: {', '.join(sorted(unsupported))}"
            )
        if query.limit == 0:
            return ProviderSearchResults((), ())
        catalog_uri = self._catalog_uri
        if catalog_uri is None:  # pragma: no cover - guarded by search
            raise AssertionError("static STAC catalog is not configured")
        queue: deque[str] = deque((catalog_uri,))
        discovered: set[str] = {catalog_uri}
        visited: set[str] = set()
        documents_read = 0
        found: list[Resource] = []
        diagnostics: list[SearchDiagnostic] = []
        while queue:
            requested_uri = queue.popleft()
            if requested_uri in visited:
                continue
            if documents_read >= self._max_documents:
                raise ProviderResponseError(
                    "Static STAC traversal exceeded max_documents before completing"
                )
            document, response_uri = self._request_with_uri(requested_uri, {})
            documents_read += 1
            # Redirect targets are visited identities too. The final response URI
            # anchors relative links, never an untrusted advertised self link.
            if response_uri in visited:
                continue
            visited.update((requested_uri, response_uri))
            discovered.add(response_uri)
            document_type = document.get("type")
            if document_type == "Feature":
                item_id = _optional_string(document.get("id"))
                try:
                    if not self._matches_static_query(document, query, collections):
                        continue
                    item_results = self._item_resources(
                        document,
                        response_uri,
                        {},
                        item_href=response_uri,
                    )
                except (ConfigValidationError, ProviderResponseError):
                    diagnostics.append(
                        SearchDiagnostic(
                            source_id=self.adapter_type,
                            skipped_conditions=frozenset(),
                            reason="item_skipped",
                            resource_identifier=item_id,
                            detail="invalid_item",
                        )
                    )
                    continue
                if not item_results:
                    diagnostics.append(
                        SearchDiagnostic(
                            source_id=self.adapter_type,
                            skipped_conditions=frozenset(),
                            reason="item_skipped",
                            resource_identifier=item_id,
                            detail="missing_data_asset",
                        )
                    )
                for result in item_results:
                    found.append(result)
                    if query.limit is not None and len(found) >= query.limit:
                        return ProviderSearchResults(tuple(found), tuple(diagnostics))
                continue
            parsed_catalog = self._parse_catalog(document, response_uri)
            for link in parsed_catalog.links:
                if link.rel not in {"child", "item"}:
                    continue
                try:
                    target = self._http_href(
                        link.get_absolute_href() if link.get_target_str() else None
                    )
                except ValueError as error:
                    raise ProviderResponseError(
                        "Static STAC link href is invalid"
                    ) from error
                if target not in discovered:
                    discovered.add(target)
                    queue.append(target)
        return ProviderSearchResults(tuple(found), tuple(diagnostics))

    def _item_resources(
        self,
        item: JsonObject,
        response_uri: str,
        query_parameters: dict[str, Any],
        *,
        item_href: str | None = None,
    ) -> tuple[Resource, ...]:
        item_id = _optional_string(item.get("id"))
        if item_id is None or not item_id.strip():
            raise ProviderResponseError("STAC item id must be a non-empty string")
        collection_id = _optional_string(item.get("collection"))
        if collection_id is None or not collection_id.strip():
            raise ProviderResponseError("STAC collection must be a non-empty string")
        properties = self._object(item.get("properties"), "STAC properties")
        parsed = self._parse_item(item, response_uri)
        title = _optional_string(properties.get("title")) or item_id
        results: list[Resource] = []
        for asset_key in self._data_asset_keys(item):
            asset = self._asset(item, asset_key)
            uri, format_name, media_type = self._delivery(asset, parsed, asset_key)
            parameters = {
                "collection_id": collection_id,
                "item_id": item_id,
                "asset_key": asset_key,
            }
            if item_href is not None:
                parameters["item_href"] = item_href
            provenance = Provenance(
                provider="stac",
                dataset_identifier=collection_id,
                resource_identifier=f"{item_id}:{asset_key}",
                api_endpoint=self._catalog_uri or self._endpoint,
                original_url=uri,
                query_parameters=query_parameters,
                adapter="stac",
                raw=item,
            )
            results.append(
                resource_from_delivery(
                    reference=Reference(
                        self.adapter_type,
                        dataset_identifier=collection_id,
                        resource_identifier=f"{item_id}:{asset_key}",
                        parameters=parameters,
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
        return tuple(results)

    def _matches_static_query(
        self,
        item: JsonObject,
        query: SearchQuery,
        collections: Sequence[str],
    ) -> bool:
        if collections and item.get("collection") not in collections:
            return False
        if query.bbox is not None:
            raw_bbox = item.get("bbox")
            if not isinstance(raw_bbox, list):
                return False
            bbox_values = cast(list[Any], raw_bbox)
            if len(bbox_values) != 4:
                return False
            if not all(
                type(value) in {int, float} and isfinite(value) for value in bbox_values
            ):
                return False
            item_bbox = bbox_values
            query_bbox = query.bbox
            if item_bbox[3] < query_bbox[1] or query_bbox[3] < item_bbox[1]:
                return False
            # CRS84 boxes crossing the antimeridian have west > east.
            # Compare their two longitude intervals, not an inverted interval.
            item_intervals = (
                ((item_bbox[0], 180), (-180, item_bbox[2]))
                if item_bbox[0] > item_bbox[2]
                else ((item_bbox[0], item_bbox[2]),)
            )
            query_intervals = (
                ((query_bbox[0], 180), (-180, query_bbox[2]))
                if query_bbox[0] > query_bbox[2]
                else ((query_bbox[0], query_bbox[2]),)
            )
            if not any(
                (west <= other_east and other_west <= east)
                or (east == 180 and other_west == -180)
                or (west == -180 and other_east == 180)
                for west, east in item_intervals
                for other_west, other_east in query_intervals
            ):
                return False
        if query.time is not None:
            properties = self._object(item.get("properties"), "STAC properties")
            instant = _stac_datetime(properties.get("datetime"))
            item_start = _stac_datetime(properties.get("start_datetime")) or instant
            item_end = _stac_datetime(properties.get("end_datetime")) or instant
            if item_start is None or item_end is None:
                return False
            query_start, query_end = query.time
            item_start, item_end = _comparable_interval(
                item_start, item_end, query_start, query_end
            )
            if query_start is not None and item_end < query_start:
                return False
            if query_end is not None and query_end < item_start:
                return False
        return True

    @staticmethod
    def _parse_item(document: JsonObject, response_uri: str) -> pystac.Item:
        try:
            # Parsing only: no migration, schema fetching, link resolution I/O,
            # or global StacIO changes. PySTAC preserves the input dictionary.
            return pystac.Item.from_dict(
                dict(document), href=response_uri, migrate=False
            )
        except (
            pystac.STACError,
            pystac.STACTypeError,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as error:
            raise ProviderResponseError("Invalid STAC Item document") from error

    @staticmethod
    def _parse_catalog(document: JsonObject, response_uri: str) -> pystac.Catalog:
        try:
            if document.get("type") == "Collection":
                return pystac.Collection.from_dict(
                    dict(document), href=response_uri, migrate=False
                )
            return pystac.Catalog.from_dict(
                dict(document), href=response_uri, migrate=False
            )
        except (
            pystac.STACError,
            pystac.STACTypeError,
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
        ) as error:
            raise ProviderResponseError(
                "Invalid static STAC Catalog document"
            ) from error

    @staticmethod
    def _http_href(href: str | None) -> str:
        if (
            not isinstance(href, str)
            or not href.casefold().startswith(("https://", "http://"))
            or not is_valid_http_authority(href)
        ):
            raise ValueError("STAC href must have a valid HTTP(S) authority")
        return href

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
        self, asset: JsonObject, item: pystac.Item, asset_key: str
    ) -> tuple[str, str | None, str | None]:
        self._required_string(asset, "href")
        try:
            # The parsed Asset has a non-empty href and an Item with an
            # absolute response URI, so PySTAC can always resolve it.
            uri = cast(str, item.assets[asset_key].get_absolute_href())
            urlsplit(uri)  # Reject malformed authorities; preserve non-HTTP schemes.
        except ValueError as error:
            raise ProviderResponseError("STAC asset href is invalid") from error
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


def _stac_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _comparable_interval(
    item_start: datetime,
    item_end: datetime,
    query_start: datetime | None,
    query_end: datetime | None,
) -> tuple[datetime, datetime]:
    query_value = query_start or query_end
    if query_value is None:
        return item_start, item_end
    query_is_aware = query_value.utcoffset() is not None
    item_is_aware = item_start.utcoffset() is not None
    if query_is_aware and item_is_aware:
        return item_start.astimezone(timezone.utc), item_end.astimezone(timezone.utc)
    if not query_is_aware and item_is_aware:
        return item_start.replace(tzinfo=None), item_end.replace(tzinfo=None)
    if query_is_aware and not item_is_aware:
        return (
            item_start.replace(tzinfo=timezone.utc),
            item_end.replace(tzinfo=timezone.utc),
        )
    return item_start, item_end
