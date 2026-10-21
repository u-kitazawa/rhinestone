"""Shared CKAN Action API operations, independent of Provider configuration."""

from collections.abc import Callable, Mapping
from typing import Any, cast
from urllib.parse import urlsplit

from ..._uri import is_valid_http_authority
from ...errors import ProviderResponseError
from ...models import (
    Metadata,
    Provenance,
    ProviderSearchResults,
    Reference,
    Resource,
    SearchDiagnostic,
    SearchQuery,
)
from ...representations import (
    canonical_format,
    container_from_media_type,
    format_from_media_type,
)
from ...resolution import resource_from_delivery
from ._ckan_resources import (
    filtered_resource_package,
    package_objects,
    resource_objects,
)
from .base import JsonObject


class CkanClient:
    """Share CKAN documents and resource expansion through an injected request.

    Provider adapters own configuration, schema validation, credentials, and
    search strategy. This client neither creates nor calls another adapter.
    """

    def __init__(
        self,
        request: Callable[[str, Mapping[str, Any]], JsonObject],
        adapter_type: str,
    ) -> None:
        self._request = request
        self.adapter_type = adapter_type

    @staticmethod
    def _object(value: Any, context: str) -> JsonObject:
        if not isinstance(value, Mapping):
            raise ProviderResponseError(
                f"{context} must be an object; provider response shape is invalid"
            )
        return cast(JsonObject, value)

    def action(self, endpoint: str, action: str, params: Mapping[str, Any]) -> Any:
        response = self._request(f"{endpoint}/api/3/action/{action}", params)
        if response.get("success") is not True:
            error = response.get("error")
            if isinstance(error, Mapping):
                message = cast(Mapping[str, Any], error).get(
                    "message", "unknown CKAN error"
                )
            else:
                message = "unknown CKAN error"
            raise ProviderResponseError(str(message))
        if "result" not in response:
            raise ProviderResponseError("CKAN response has no result")
        return response["result"]

    def load(self, reference: Reference, endpoint: str, resource_id: str) -> Resource:
        """Load a validated resource identifier and its parent package."""
        resource = self._object(
            self.action(endpoint, "resource_show", {"id": resource_id}),
            "CKAN resource",
        )
        package_id = self._response_string(resource, "package_id")
        package = self._object(
            self.action(endpoint, "package_show", {"id": package_id}),
            "CKAN package",
        )
        uri, format_name, media_type, archive = self._delivery(resource)
        organization = package.get("organization")
        publisher = (
            cast(Mapping[str, Any], organization).get("title")
            if isinstance(organization, Mapping)
            else None
        )
        metadata = Metadata(
            title=_optional_string(package.get("title")),
            description=_optional_string(package.get("notes")),
            publisher=_optional_string(publisher),
            license=_optional_string(package.get("license_title")),
            raw=package,
        )
        provenance = Provenance(
            provider="ckan",
            dataset_identifier=package_id,
            resource_identifier=resource_id,
            api_endpoint=endpoint,
            original_url=uri,
            query_parameters={"resource_id": resource_id},
            adapter="ckan",
            raw={"resource": resource, "package": package},
        )
        return resource_from_delivery(
            reference=replace_reference(reference, package_id, resource_id),
            uri=uri,
            format=format_name,
            media_type=media_type,
            metadata=metadata,
            provenance=provenance,
            archive=archive,
        )

    def search(
        self, endpoint: str, query: SearchQuery, params: Mapping[str, Any]
    ) -> tuple[Resource, ...] | ProviderSearchResults:
        """Expand pages for the caller's explicit CKAN package query."""
        if query.limit == 0:
            return ()
        found: list[Resource] = []
        diagnostics: list[SearchDiagnostic] = []
        start = 0
        while True:
            page_params = dict(params)
            if start:
                page_params["start"] = start
            result = self._object(
                self.action(endpoint, "package_search", page_params),
                "CKAN search result",
            )
            packages = package_objects(
                result.get("results"), self.adapter_type, diagnostics
            )
            for package in packages:
                if package is None:
                    continue
                resources = resource_objects(
                    package.get("resources"), self.adapter_type, diagnostics
                )
                invalid_urls = {
                    index
                    for index, resource in enumerate(resources)
                    if self._invalid_resource_url(resource)
                }
                safe_package = filtered_resource_package(package, resources)
                if invalid_urls:
                    safe_package = {
                        **package,
                        "resources": [
                            (
                                {**resource, "url": "[redacted]"}
                                if index in invalid_urls
                                else resource
                            )
                            for index, resource in enumerate(resources)
                        ],
                    }
                for index, resource in enumerate(resources):
                    item = self.search_resource_result(
                        safe_package,
                        resource,
                        endpoint,
                        query,
                        diagnostics,
                        invalid_resource_url=index in invalid_urls,
                    )
                    if item is None:
                        continue
                    found.append(item)
                    if query.limit is not None and len(found) == query.limit:
                        return search_results(found, diagnostics)
            if query.limit is None:
                return search_results(found, diagnostics)
            total = result.get("count")
            if type(total) is not int or total < 0:
                raise ProviderResponseError(
                    "CKAN search result count must be an integer"
                )
            if start + len(packages) >= total:
                return search_results(found, diagnostics)
            if not packages:
                raise ProviderResponseError(
                    "CKAN search result is empty before its declared count"
                )
            start += len(packages)

    def search_resource_result(
        self,
        package: JsonObject,
        resource: JsonObject,
        endpoint: str,
        query: SearchQuery,
        diagnostics: list[SearchDiagnostic],
        *,
        invalid_resource_url: bool = False,
    ) -> Resource | None:
        resource_id = resource.get("id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            diagnostics.append(
                SearchDiagnostic(
                    source_id=self.adapter_type,
                    skipped_conditions=frozenset(),
                    reason="item_skipped",
                    detail="missing_resource_id",
                )
            )
            return None
        if invalid_resource_url:
            diagnostics.append(
                SearchDiagnostic(
                    source_id=self.adapter_type,
                    skipped_conditions=frozenset(),
                    reason="item_skipped",
                    resource_identifier=resource_id,
                    detail="invalid_resource_url",
                )
            )
            return None
        return self._resource_result(package, resource, endpoint, query)

    def _resource_result(
        self,
        package: JsonObject,
        resource: JsonObject,
        endpoint: str,
        query: SearchQuery,
    ) -> Resource | None:
        """Expand one declared CKAN resource without changing package metadata."""
        # search_resource_result has already validated the resource identity.
        resource_id = cast(str, resource["id"])
        media_type = _optional_string(resource.get("mimetype"))
        format_name = canonical_format(resource.get("format")) or (
            format_from_media_type(media_type)
        )
        formats: frozenset[str] = (
            frozenset({format_name}) if format_name else frozenset()
        )
        if query.format is not None and not matches_query_formats(formats, query):
            return None
        package_id = _optional_string(package.get("id"))
        raw_uri = resource.get("url")
        if isinstance(raw_uri, str) and raw_uri:
            uri, selected_format, selected_media_type, archive = self._delivery(
                resource
            )
        else:
            uri = f"rhinestone-reference:{self.adapter_type}:{resource_id}"
            selected_format = format_name
            selected_media_type = media_type
            archive = None
        metadata = Metadata(
            title=_optional_string(package.get("title")) or resource_id,
            description=_optional_string(package.get("notes")),
            raw=package,
        )
        provenance = Provenance(
            provider="ckan",
            dataset_identifier=package_id,
            resource_identifier=resource_id,
            api_endpoint=endpoint,
            original_url=uri,
            adapter="ckan",
            raw={"package": package, "resource": resource},
        )
        reference = Reference(
            self.adapter_type,
            dataset_identifier=package_id,
            resource_identifier=resource_id,
            parameters={"resource_id": resource_id},
        )
        if not isinstance(raw_uri, str) or not raw_uri:
            return Resource(
                uri=uri,
                format=selected_format,
                media_type=selected_media_type,
                metadata=metadata,
                provenance=provenance,
                access_plan=None,
                reference=reference,
            )
        return resource_from_delivery(
            reference=reference,
            uri=uri,
            format=selected_format,
            media_type=selected_media_type,
            metadata=metadata,
            provenance=provenance,
            archive=archive,
        )

    def _delivery(
        self, resource: JsonObject
    ) -> tuple[str, str | None, str | None, str | None]:
        uri = self._response_string(resource, "url")
        if not self._is_safe_resource_url(uri):
            raise ProviderResponseError(
                "CKAN resource URL has an invalid HTTP(S) authority"
            )
        media_type = _optional_string(resource.get("mimetype"))
        archive = container_from_media_type(media_type)
        return (
            uri,
            canonical_format(resource.get("format"))
            or format_from_media_type(media_type),
            media_type,
            archive,
        )

    @staticmethod
    def _response_string(response: Mapping[str, Any], name: str) -> str:
        value = response.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ProviderResponseError(
                f"CKAN resource {name} must be a non-empty string"
            )
        return value

    @staticmethod
    def _invalid_resource_url(resource: JsonObject) -> bool:
        if "url" not in resource or resource.get("url") is None:
            return False
        value = resource.get("url")
        return (
            not isinstance(value, str)
            or not value.strip()
            or not CkanClient._is_safe_resource_url(value)
        )

    @staticmethod
    def _is_safe_resource_url(uri: str) -> bool:
        try:
            parsed = urlsplit(uri)
        except (TypeError, ValueError, UnicodeError):
            return False
        return (
            parsed.username is None
            and parsed.password is None
            and is_valid_http_authority(uri)
        )


def package_search_params(query: SearchQuery) -> dict[str, Any]:
    """Build provider-specific CKAN package search parameters."""
    params: dict[str, Any] = {}
    if query.text is not None:
        params["q"] = query.text
    if query.bbox is not None:
        params["ext_bbox"] = ",".join(str(value) for value in query.bbox)
    if query.limit is not None:
        params["rows"] = query.limit
    return params


def search_results(
    found: list[Resource], diagnostics: list[SearchDiagnostic]
) -> tuple[Resource, ...] | ProviderSearchResults:
    results = tuple(found)
    if diagnostics:
        return ProviderSearchResults(results, tuple(diagnostics))
    return results


def matches_query_formats(formats: frozenset[str], query: SearchQuery) -> bool:
    requested = {value.value for value in query.expanded_formats}
    return bool(formats & requested) or (not formats and "unknown" in requested)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def replace_reference(
    reference: Reference, dataset_identifier: str, resource_identifier: str
) -> Reference:
    return Reference(
        reference.provider_id,
        dataset_identifier=dataset_identifier,
        resource_identifier=resource_identifier,
        parameters=reference.parameters,
    )
