"""Discovery adapter for the Japanese cross-CKAN search service."""

from typing import Any, Dict, List, Optional, Tuple

from ....errors import (
    ConfigValidationError,
    ProviderResponseError,
    UnsupportedSourceError,
)
from ....models import Config, Metadata, Provenance, SearchQuery, SearchResult, Source
from ....security import DestinationPolicy
from .._uri import has_embedded_credentials
from ..base import JsonObject, JsonTransport, ProviderAdapter
from .parsing import optional_string, organization_title, resource_format

DEFAULT_ENDPOINT = "https://search.ckan.jp/backend/api"


class SearchCkanJpAdapter(ProviderAdapter):
    """Discover executable direct resources from search.ckan.jp metadata."""

    adapter_type = "search-ckan-jp"
    search_conditions = frozenset({"text", "limit"})
    required_search_conditions = frozenset({"text"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = DEFAULT_ENDPOINT,
        destination_policy: Optional[DestinationPolicy] = None,
    ) -> None:
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            destination_policy=destination_policy,
        )

    def load(self, config: Config) -> Source:
        """Reject direct loading because this adapter is discovery-only."""
        raise UnsupportedSourceError(
            "search-ckan-jp is a discovery-only source and cannot resolve resources"
        )

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        """Search the official search.ckan.jp endpoint using text criteria."""
        if query.text is None:
            raise ConfigValidationError(
                "search-ckan-jp requires a text condition for discovery"
            )
        endpoint = self._endpoint_from({}, DEFAULT_ENDPOINT)
        params: Dict[str, Any] = {"q": query.text}
        if query.limit is not None:
            params["rows"] = query.limit
        response = self._request(f"{endpoint}/package_search", params)
        if response.get("success") is not True:
            raise ProviderResponseError("search.ckan.jp search was not successful")
        result = self._object(response.get("result"), "search.ckan.jp result")
        packages = self._objects(result.get("results"), "search.ckan.jp results")
        found: List[SearchResult] = []
        for package in packages:
            found.extend(self._package_results(package, endpoint, params))
        return tuple(found[: query.limit])

    def _package_results(
        self,
        package: JsonObject,
        endpoint: str,
        params: Dict[str, Any],
    ) -> Tuple[SearchResult, ...]:
        package_id = optional_string(package.get("xckan_original_id"))
        if package_id is None:
            package_id = optional_string(package.get("id"))
        title = optional_string(package.get("title")) or package_id
        if title is None:
            return ()
        description = optional_string(package.get("notes"))
        publisher = organization_title(package.get("organization"))
        license_name = optional_string(package.get("license_title"))
        site_url = optional_string(package.get("xckan_site_url"))
        resources = self._objects(package.get("resources"), "search.ckan.jp resources")
        found: List[SearchResult] = []
        for resource in resources:
            resource_id = optional_string(resource.get("id"))
            uri = optional_string(resource.get("url"))
            format_name = resource_format(resource)
            if resource_id is None or uri is None or format_name is None:
                continue
            if has_embedded_credentials(uri):
                raise ProviderResponseError(
                    "search.ckan.jp resource URL must not contain embedded credentials"
                )
            metadata = Metadata(
                title=title,
                description=description,
                publisher=publisher,
                license=license_name,
                raw=package,
            )
            provenance = Provenance(
                provider=optional_string(package.get("xckan_site_name"))
                or "search-ckan-jp",
                dataset_identifier=package_id,
                resource_identifier=resource_id,
                api_endpoint=endpoint,
                original_url=site_url or uri,
                query_parameters=params,
                adapter=self.adapter_type,
                raw={"catalog": package, "resource": resource},
            )
            target_settings: Dict[str, Any] = {
                "uri": uri,
                "format": format_name,
                "metadata": {
                    "title": title,
                    "description": description,
                    "publisher": publisher,
                    "license": license_name,
                    "raw": package,
                },
            }
            media_type = optional_string(resource.get("mimetype"))
            if media_type is not None:
                target_settings["media_type"] = media_type
            found.append(
                SearchResult(
                    title=title,
                    description=description,
                    discovered_by=self.adapter_type,
                    target=Config("direct", target_settings),
                    metadata=metadata,
                    provenance=provenance,
                    raw_metadata={"catalog": package, "resource": resource},
                )
            )
        return tuple(found)
