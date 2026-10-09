"""ODPT v4 service knowledge; data requests are executed only by open."""

from collections.abc import Mapping
from typing import Any, cast

from ....errors import ConfigValidationError
from ....models import AccessPlan, Metadata, Provenance, Reference, Resource
from ....registry import CredentialRegistry
from ....resolution import resource_from_delivery
from .._knowledge import string
from ..base import ProviderAdapter
from .validation import filter_mapping, required_string, string_mapping


class OdptAdapter(ProviderAdapter):
    """Create explicit ODPT JSON service access plans."""

    adapter_type = "odpt"

    def __init__(
        self,
        endpoint: str | None = None,
        resource_types: Mapping[str, str] | None = None,
        filter_fields: Mapping[str, Any] | None = None,
        spec_source: str | None = None,
        terms_url: str | None = None,
    ) -> None:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ConfigValidationError("ODPT endpoint must be configured")
        super().__init__(get_json=lambda url, params: None, endpoint=endpoint)
        self._resource_types = string_mapping(resource_types, "resource_types")
        self._filter_fields = filter_mapping(filter_fields)
        required = ("station", "railway", "train")
        if any(
            name not in self._resource_types or name not in self._filter_fields
            for name in required
        ):
            raise ConfigValidationError(
                "ODPT catalog must define station, railway, and train"
            )
        self._spec_source = required_string(spec_source, "spec_source")
        self._terms_url = required_string(terms_url, "terms_url")

    def load(self, reference: Reference) -> Resource:
        """Build a queryable Resource from an ODPT dataset declaration."""
        settings = self._reference_parameters(reference)
        dataset = string(settings, "dataset")
        credential = string(settings, "credential")
        filters_value = settings.get("filters", {})
        if not isinstance(filters_value, Mapping):
            raise ConfigValidationError("ODPT filters must be an object")
        filters = cast(Mapping[str, Any], filters_value)
        if set(filters) - self._filter_fields[dataset]:
            raise ConfigValidationError("Unsupported ODPT filter")
        endpoint = self._endpoint_from(settings)
        uri = endpoint + "/" + self._resource_types[dataset]
        raw = {
            "resource_type": self._resource_types[dataset],
            "filters": dict(filters),
            "spec_source": self._spec_source,
            "terms_url": self._terms_url,
        }
        identifier = self._resource_types[dataset]
        provenance = Provenance(
            provider=self.adapter_type,
            dataset_identifier=identifier,
            api_endpoint=uri,
            original_url=uri,
            adapter=self.adapter_type,
            raw=raw,
        )
        return resource_from_delivery(
            reference=Reference(
                reference.provider_id,
                dataset_identifier=identifier,
                resource_identifier=identifier,
                parameters=reference.parameters,
            ),
            uri=uri,
            format="api",
            media_type="application/json",
            metadata=Metadata(
                title=identifier,
                publisher=self.adapter_type,
                raw=raw,
            ),
            provenance=provenance,
            kind="service-query",
            options={
                "params": dict(filters),
                "response_type": "array",
                "endpoint": uri,
            },
            service=self.adapter_type,
            credential=credential,
        )

    @staticmethod
    def prepare_request(
        plan: AccessPlan,
        credentials: CredentialRegistry,
    ) -> tuple[Mapping[str, Any], Mapping[str, str]]:
        """Convert an ODPT service plan into request parameters and headers."""
        expected_uri = plan.options.get("endpoint")
        if (
            plan.kind != "service-query"
            or plan.service != OdptAdapter.adapter_type
            or not isinstance(expected_uri, str)
            or plan.uri != expected_uri
        ):
            raise ConfigValidationError(
                "Credential destination is not an ODPT endpoint"
            )
        params_value = plan.options.get("params")
        credential = plan.credential
        if not isinstance(params_value, Mapping) or not isinstance(credential, str):
            raise ConfigValidationError("ODPT service plan is incomplete")
        params: dict[str, Any] = dict(cast(Mapping[str, Any], params_value))
        params["acl:consumerKey"] = credentials.get(credential)
        return params, {}
