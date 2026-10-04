"""CKAN Action API source adapter."""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import ConfigValidationError, ProviderResponseError
from ....models import (
    Config,
    Metadata,
    Provenance,
    ResourceCandidate,
    Result,
    SearchQuery,
    Source,
)
from ....registry import CredentialRegistry
from ....representations import (
    canonical_format,
    container_from_media_type,
    format_from_media_type,
)
from ....security import DestinationPolicy
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

    def load(self, config: Config) -> Source:
        """Load one CKAN resource and its parent package metadata."""
        settings = self._config_settings(config)
        endpoint = self._endpoint_from(settings)
        resource_id = self._required_string(settings, "resource_id")
        resource = self._object(
            self._action(endpoint, "resource_show", {"id": resource_id}),
            "CKAN resource",
        )
        package_id = self._required_string(resource, "package_id")
        package = self._object(
            self._action(endpoint, "package_show", {"id": package_id}),
            "CKAN package",
        )
        candidate = self._candidate(resource)
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
            original_url=candidate.uri,
            query_parameters={"resource_id": resource_id},
            adapter="ckan",
            raw={"resource": resource, "package": package},
        )
        return Source(
            metadata=metadata,
            candidates=(candidate,),
            capabilities=frozenset({"download", "search"}),
            provenance=provenance,
            raw_metadata={"resource": resource, "package": package},
        )

    def search(self, query: SearchQuery) -> tuple[Result, ...]:
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
        found: list[Result] = []
        start = 0
        while True:
            page_params = dict(params)
            if start:
                page_params["start"] = start
            result = self._object(
                self._action(endpoint, "package_search", page_params),
                "CKAN search result",
            )
            packages = self._objects(result.get("results"), "CKAN search results")
            for package in packages:
                resources = self._objects(package.get("resources"), "CKAN resources")
                for resource in resources:
                    resource_id = self._required_string(resource, "id")
                    media_type = _optional_string(resource.get("mimetype"))
                    format_name = canonical_format(resource.get("format")) or (
                        format_from_media_type(media_type)
                    )
                    formats: frozenset[str] = (
                        frozenset({format_name}) if format_name else frozenset()
                    )
                    if query.format is not None and not self._matches_query_formats(
                        formats, query
                    ):
                        continue
                    found.append(
                        Result(
                            title=_optional_string(package.get("title")) or resource_id,
                            description=_optional_string(package.get("notes")),
                            discovered_by=self.adapter_type,
                            target=Config(
                                self.adapter_type, {"resource_id": resource_id}
                            ),
                            metadata=Metadata(
                                title=_optional_string(package.get("title")),
                                raw=package,
                            ),
                            provenance=Provenance(
                                provider="ckan",
                                dataset_identifier=_optional_string(package.get("id")),
                                resource_identifier=resource_id,
                                api_endpoint=endpoint,
                                adapter="ckan",
                                raw=package,
                            ),
                            formats=formats,
                            raw_metadata={"package": package, "resource": resource},
                        )
                    )
                    if query.limit is not None and len(found) == query.limit:
                        return tuple(found)
            if query.limit is None:
                return tuple(found)
            total = result.get("count")
            if type(total) is not int or total < 0:
                raise ProviderResponseError(
                    "CKAN search result count must be an integer"
                )
            if start + len(packages) >= total:
                return tuple(found)
            if not packages:
                raise ProviderResponseError(
                    "CKAN search result is empty before its declared count"
                )
            start += len(packages)

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

    def _candidate(self, resource: JsonObject) -> ResourceCandidate:
        uri = self._required_string(resource, "url")
        media_type = _optional_string(resource.get("mimetype"))
        attributes = dict(resource)
        archive = container_from_media_type(media_type)
        if archive is not None:
            attributes["archive"] = archive
        return ResourceCandidate(
            uri=uri,
            format=canonical_format(resource.get("format"))
            or format_from_media_type(media_type),
            media_type=media_type,
            attributes=attributes,
        )

    @staticmethod
    def _matches_query_formats(formats: frozenset[str], query: SearchQuery) -> bool:
        requested = {value.value for value in query.expanded_formats}
        return bool(formats & requested) or (not formats and "unknown" in requested)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None
