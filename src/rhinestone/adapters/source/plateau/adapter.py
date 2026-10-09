"""PLATEAU distributions published through the G Spatial CKAN catalog."""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    ResourceNotFoundError,
)
from ....models import Metadata, Provenance, Reference, Resource, SearchQuery
from ....registry import CredentialRegistry
from ....representations import canonical_format
from ....resolution import resource_from_delivery
from ....security import DestinationPolicy
from ...knowledge import KnowledgeAdapterRegistry
from .._knowledge import entry_point, resolve_knowledge, string
from ..base import JsonTransport
from ..ckan import CkanAdapter


class PlateauAdapter(CkanAdapter):
    """Interpret PLATEAU datasets exposed through a CKAN-compatible API."""

    adapter_type = "plateau"

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
        knowledge: KnowledgeAdapterRegistry | None = None,
    ) -> None:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ConfigValidationError("PLATEAU endpoint must be configured")
        super().__init__(
            get_json,
            endpoint=endpoint,
            credential=credential,
            credential_header=credential_header,
            credential_scheme=credential_scheme,
            credentials=credentials,
            destination_policy=destination_policy,
            provider_id=provider_id,
        )
        self._knowledge = knowledge or KnowledgeAdapterRegistry()

    def _package_search_params(self, query: SearchQuery) -> dict[str, Any]:
        """Restrict package search to the catalog's explicit PLATEAU tag."""
        params = super()._package_search_params(query)
        params["fq"] = "tags:PLATEAU"
        return params

    def load(self, reference: Reference) -> Resource:
        """Load one PLATEAU resource and preserve its CityGML metadata."""
        settings = self._reference_parameters(
            reference,
            dataset_key=(
                None if reference.resource_identifier is not None else "dataset_id"
            ),
            resource_key="resource_id",
        )
        endpoint = self._endpoint_from(settings)
        resource_id: str | None = None
        if "resource_id" in settings:
            resource_id = string(settings, "resource_id")
            resource = self._object(
                self._action(endpoint, "resource_show", {"id": resource_id}),
                "CKAN resource",
            )
            package_id = string(resource, "package_id")
        else:
            package_id = string(settings, "dataset_id")
        package = self._object(
            self._action(endpoint, "package_show", {"id": package_id}),
            "CKAN package",
        )
        resources = self._objects(package.get("resources"), "CKAN resources")
        member = entry_point(settings)
        knowledge = resolve_knowledge(settings, self._knowledge)
        selected: list[tuple[Mapping[str, Any], str]] = []
        for item in resources:
            identifier = string(item, "id")
            format_name = canonical_format(string(item, "format"))
            assert format_name is not None
            matches = resource_id is None or identifier == resource_id
            if "format" in settings:
                matches = matches and format_name == canonical_format(
                    string(settings, "format")
                )
            if matches:
                selected.append((item, format_name))
        if not selected:
            raise ResourceNotFoundError("No PLATEAU distribution matches Reference")
        if len(selected) != 1:
            raise AmbiguousResourceError(
                f"PLATEAU dataset has {len(selected)} matching distributions; "
                "set Reference.resource_identifier or format"
            )
        item, format_name = selected[0]
        resource_identifier = string(item, "id")
        uri = string(item, "url")
        raw: Mapping[str, Any] = {
            "package": package,
            "distribution_provider": "G Spatial Information Center",
        }
        metadata = Metadata(
            title=cast(str | None, package.get("title")),
            description=cast(str | None, package.get("notes")),
            publisher=self.adapter_type,
            license=cast(str | None, package.get("license_title")),
            raw={**raw, "knowledge": knowledge},
        )
        provenance = Provenance(
            provider=self.adapter_type,
            dataset_identifier=package_id,
            resource_identifier=resource_identifier,
            api_endpoint=endpoint,
            original_url=uri,
            adapter=self.adapter_type,
            raw=raw,
        )
        return resource_from_delivery(
            reference=Reference(
                reference.provider_id,
                dataset_identifier=package_id,
                resource_identifier=resource_identifier,
                parameters=reference.parameters,
            ),
            uri=uri,
            format=format_name,
            media_type=cast(str | None, item.get("mimetype")),
            metadata=metadata,
            provenance=provenance,
            kind="file",
            archive=cast(str | None, settings.get("archive")),
            options={} if member is None else {"entry_point": member},
        )
