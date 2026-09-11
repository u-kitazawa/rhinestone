"""CKAN Action API source adapter."""

from typing import Any, Dict, List, Mapping, Optional, Tuple, cast

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

_FORMAT_ALIASES = {"geopackage": "gpkg"}


class CkanAdapter(ProviderAdapter):
    adapter_type = "ckan"
    search_conditions = frozenset({"text", "limit"})

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = None,
        api_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-CKAN-API-Key",
        credential: Optional[str] = None,
        credential_header: Optional[str] = None,
        credential_scheme: Optional[str] = None,
        credentials: Optional[CredentialRegistry] = None,
        destination_policy: Optional[DestinationPolicy] = None,
        provider_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            get_json=get_json,
            endpoint=endpoint,
            api_token=api_token,
            api_key=api_key,
            api_key_header=api_key_header,
            token_scheme="",
            credential=credential,
            credential_header=credential_header,
            credential_scheme=credential_scheme,
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

    def search(self, query: SearchQuery) -> Tuple[SearchResult, ...]:
        endpoint = self._endpoint_from({}, self._endpoint)
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported CKAN search conditions: {', '.join(sorted(unsupported))}"
            )
        params: Dict[str, Any] = {}
        if query.text is not None:
            params["q"] = query.text
        if query.limit is not None:
            params["rows"] = query.limit
        result = self._object(
            self._action(endpoint, "package_search", params), "CKAN search result"
        )
        packages = self._objects(result.get("results"), "CKAN search results")
        found: List[SearchResult] = []
        for package in packages:
            resources = self._objects(package.get("resources"), "CKAN resources")
            for resource in resources:
                resource_id = self._required_string(resource, "id")
                found.append(
                    SearchResult(
                        title=_optional_string(package.get("title")) or resource_id,
                        description=_optional_string(package.get("notes")),
                        discovered_by=self.adapter_type,
                        target=Config(self.adapter_type, {"resource_id": resource_id}),
                        metadata=Metadata(
                            title=_optional_string(package.get("title")), raw=package
                        ),
                        provenance=Provenance(
                            provider="ckan",
                            dataset_identifier=_optional_string(package.get("id")),
                            resource_identifier=resource_id,
                            api_endpoint=endpoint,
                            adapter="ckan",
                            raw=package,
                        ),
                    )
                )
        return tuple(found)

    def _candidate(self, resource: JsonObject) -> ResourceCandidate:
        uri = self._required_string(resource, "url")
        return ResourceCandidate(
            uri=uri,
            format=canonical_format(resource.get("format")),
            media_type=_optional_string(resource.get("mimetype")),
            attributes=resource,
        )


def _optional_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def canonical_format(value: Any) -> Optional[str]:
    format_name = _optional_string(value)
    if format_name is None:
        return None
    normalized = format_name.strip().lower()
    return _FORMAT_ALIASES.get(normalized, normalized)
