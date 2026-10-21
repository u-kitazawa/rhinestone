"""CKAN Provider configuration and package search."""

from ....errors import ConfigValidationError
from ....models import ProviderSearchResults, Reference, Resource, SearchQuery
from ....registry import CredentialRegistry
from ....security import DestinationPolicy
from .._ckan import CkanClient, package_search_params
from ..base import JsonTransport, ProviderAdapter


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
        self._ckan = CkanClient(self._request, self.adapter_type)

    def load(self, reference: Reference) -> Resource:
        """Validate the Reference before loading the selected CKAN resource."""
        settings = self._reference_parameters(reference, resource_key="resource_id")
        endpoint = self._endpoint_from(settings)
        resource_id = self._required_string(settings, "resource_id")
        return self._ckan.load(reference, endpoint, resource_id)

    def search(
        self, query: SearchQuery
    ) -> tuple[Resource, ...] | ProviderSearchResults:
        """Search CKAN packages using the configured endpoint and capabilities."""
        endpoint = self._endpoint_from({}, self._endpoint)
        unsupported = query.supplied_conditions - self.search_conditions
        if unsupported:
            raise ConfigValidationError(
                f"Unsupported CKAN search conditions: {', '.join(sorted(unsupported))}"
            )
        return self._ckan.search(endpoint, query, package_search_params(query))
