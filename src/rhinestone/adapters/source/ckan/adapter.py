"""CKAN Action API source adapter."""

from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlsplit

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
from ....representations import (
    canonical_format,
    container_from_media_type,
    format_from_media_type,
)
from ....resolution import resource_from_delivery
from ....security import DestinationPolicy
from .._ckan_resources import package_objects, resource_objects
from ..base import JsonObject, JsonTransport, ProviderAdapter


class CkanAdapter(ProviderAdapter):
    """Interpret CKAN Action API package and resource responses."""

    adapter_type = "ckan"
    search_conditions = frozenset({"text", "format", "limit"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: str | None = None,
        spatial_search: bool = False,
        credential: str | None = None,
        credential_header: str | None = None,
        credential_scheme: str | None = None,
        credentials: CredentialRegistry | None = None,
        destination_policy: DestinationPolicy | None = None,
        provider_id: str | None = None,
    ) -> None:
        if type(spatial_search) is not bool:
            raise ConfigValidationError("CKAN spatial_search must be a boolean")
        self.search_conditions = (
            frozenset({"text", "bbox", "format", "limit"})
            if spatial_search
            else type(self).search_conditions
        )
        self.area_text_fallback = not spatial_search
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            credential=credential,
            credential_header=credential_header,
            credential_scheme="" if credential_scheme is None else credential_scheme,
            credentials=credentials,
            destination_policy=destination_policy,
            provider_id=provider_id,
        )

    def _action(self, endpoint: str, action: str, params: Mapping[str, Any]) -> Any:
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

    def load(self, reference: Reference) -> Resource:
        """Load one CKAN resource and its parent package metadata."""
        settings = self._reference_parameters(reference, resource_key="resource_id")
        endpoint = self._endpoint_from(settings)
        resource_id = self._required_string(settings, "resource_id")
        resource = self._object(
            self._action(endpoint, "resource_show", {"id": resource_id}),
            "CKAN resource",
        )
        package_id = self._response_string(resource, "package_id")
        package = self._object(
            self._action(endpoint, "package_show", {"id": package_id}),
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
        self, query: SearchQuery
    ) -> tuple[Resource, ...] | ProviderSearchResults:
        """Search CKAN packages and return their resource-level results."""
        endpoint = self._endpoint_from({}, self._endpoint)
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported CKAN search conditions: {', '.join(sorted(unsupported))}"
            )
        if query.limit == 0:
            return ()
        params = self._package_search_params(query)
        found: list[Resource] = []
        diagnostics: list[SearchDiagnostic] = []
        start = 0
        while True:
            page_params = dict(params)
            if start:
                page_params["start"] = start
            result = self._object(
                self._action(endpoint, "package_search", page_params),
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
                safe_package: JsonObject = package
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
                    item = self._search_resource_result(
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
                        return self._search_results(found, diagnostics)
            if query.limit is None:
                return self._search_results(found, diagnostics)
            total = result.get("count")
            if type(total) is not int or total < 0:
                raise ProviderResponseError(
                    "CKAN search result count must be an integer"
                )
            if start + len(packages) >= total:
                return self._search_results(found, diagnostics)
            if not packages:
                raise ProviderResponseError(
                    "CKAN search result is empty before its declared count"
                )
            start += len(packages)

    def _search_resource_result(
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
        resource_id = self._required_string(resource, "id")
        media_type = _optional_string(resource.get("mimetype"))
        format_name = canonical_format(resource.get("format")) or (
            format_from_media_type(media_type)
        )
        formats: frozenset[str] = (
            frozenset({format_name}) if format_name else frozenset()
        )
        if query.format is not None and not self._matches_query_formats(formats, query):
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

    def _package_search_params(self, query: SearchQuery) -> dict[str, Any]:
        """Build provider-specific CKAN package search parameters."""
        params: dict[str, Any] = {}
        if query.text is not None:
            params["q"] = query.text
        if query.bbox is not None:
            params["ext_bbox"] = ",".join(str(value) for value in query.bbox)
        if query.limit is not None:
            params["rows"] = query.limit
        return params

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
            or not CkanAdapter._is_safe_resource_url(value)
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

    @staticmethod
    def _search_results(
        found: list[Resource], diagnostics: list[SearchDiagnostic]
    ) -> tuple[Resource, ...] | ProviderSearchResults:
        results = tuple(found)
        if diagnostics:
            return ProviderSearchResults(results, tuple(diagnostics))
        return results

    @staticmethod
    def _matches_query_formats(formats: frozenset[str], query: SearchQuery) -> bool:
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
