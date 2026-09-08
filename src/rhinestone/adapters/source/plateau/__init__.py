"""PLATEAU distributions published through the G Spatial CKAN catalog."""

from typing import Any, Dict, List, Mapping, Optional, cast

from ....errors import ConfigValidationError
from ....models import Config, ResourceCandidate, Source
from ....registry import CredentialRegistry
from ....security import DestinationPolicy
from .._knowledge import entry_point, source, string
from ..base import JsonTransport
from ..ckan import CkanAdapter


class PlateauAdapter(CkanAdapter):
    adapter_type = "plateau"

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = None,
        credential: Optional[str] = None,
        credential_header: Optional[str] = None,
        credential_scheme: Optional[str] = None,
        credentials: Optional[CredentialRegistry] = None,
        destination_policy: Optional[DestinationPolicy] = None,
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
        )

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        endpoint = self._endpoint_from(settings)
        resource_id: Optional[str] = None
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
        candidates: List[ResourceCandidate] = []
        for item in resources:
            identifier = string(item, "id")
            format_name = string(item, "format").lower()
            format_name = {"geopackage": "gpkg"}.get(format_name, format_name)
            matches = resource_id is None or identifier == resource_id
            if "format" in settings:
                matches = matches and format_name == string(settings, "format").lower()
            attributes: Dict[str, Any] = dict(item)
            attributes.update(
                {
                    "matches_config": matches,
                    "access_kind": "file",
                    "archive": settings.get("archive"),
                    "access_options": {"entry_point": member},
                }
            )
            candidates.append(
                ResourceCandidate(
                    string(item, "url"), format_name, item.get("mimetype"), attributes
                )
            )
        raw: Mapping[str, Any] = {
            "package": package,
            "distribution_provider": "G Spatial Information Center",
        }
        return source(
            self.adapter_type,
            package_id,
            raw,
            tuple(candidates),
            title=cast(Optional[str], package.get("title")),
            description=cast(Optional[str], package.get("notes")),
            license_name=cast(Optional[str], package.get("license_title")),
            endpoint=endpoint,
            capabilities=("download", "search"),
        )
