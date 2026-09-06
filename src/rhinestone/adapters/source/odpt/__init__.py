"""ODPT v4 service knowledge; data requests are executed only by open."""

from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple, cast

from ....errors import ConfigValidationError
from ....models import AccessPlan, Config, ResourceCandidate, Source
from ....registry import CredentialRegistry
from .._knowledge import source, string
from ..base import ProviderAdapter


class OdptAdapter(ProviderAdapter):
    adapter_type = "odpt"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        resource_types: Optional[Mapping[str, str]] = None,
        filter_fields: Optional[Mapping[str, Any]] = None,
        spec_source: Optional[str] = None,
        terms_url: Optional[str] = None,
    ) -> None:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ConfigValidationError("ODPT endpoint must be configured")
        super().__init__(get_json=lambda url, params: None, endpoint=endpoint)
        self._resource_types = _string_mapping(resource_types, "resource_types")
        self._filter_fields = _filter_mapping(filter_fields)
        required = ("station", "railway", "train")
        if any(
            name not in self._resource_types or name not in self._filter_fields
            for name in required
        ):
            raise ConfigValidationError(
                "ODPT catalog must define station, railway, and train"
            )
        self._spec_source = _required_string(spec_source, "spec_source")
        self._terms_url = _required_string(terms_url, "terms_url")

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
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
        return source(
            self.adapter_type,
            self._resource_types[dataset],
            raw,
            (
                ResourceCandidate(
                    uri,
                    "api",
                    "application/json",
                    {
                        "access_kind": "service-query",
                        "access_options": {
                            "params": dict(filters),
                            "credential": credential,
                            "response_type": "array",
                            "service": self.adapter_type,
                            "endpoint": uri,
                        },
                    },
                ),
            ),
            endpoint=uri,
            capabilities=("service-query",),
        )

    @staticmethod
    def prepare_request(
        plan: AccessPlan,
        credentials: CredentialRegistry,
    ) -> Tuple[Mapping[str, Any], Mapping[str, str]]:
        expected_uri = plan.options.get("endpoint")
        if (
            plan.kind != "service-query"
            or plan.options.get("service") != OdptAdapter.adapter_type
            or not isinstance(expected_uri, str)
            or plan.uri != expected_uri
        ):
            raise ConfigValidationError(
                "Credential destination is not an ODPT endpoint"
            )
        params_value = plan.options.get("params")
        credential = plan.options.get("credential")
        if not isinstance(params_value, Mapping) or not isinstance(credential, str):
            raise ConfigValidationError("ODPT service plan is incomplete")
        params: Dict[str, Any] = dict(cast(Mapping[str, Any], params_value))
        params["acl:consumerKey"] = credentials.get(credential)
        return params, {}


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"{name} must be a non-empty string")
    return value


def _string_mapping(value: Any, name: str) -> Dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ConfigValidationError(f"{name} must be a non-empty object")
    result: Dict[str, str] = {}
    values = cast(Mapping[Any, Any], value)
    for key, item in values.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(item, str):
            raise ConfigValidationError(f"{name} must map strings to strings")
        if not item.strip():
            raise ConfigValidationError(f"{name} values must be non-empty strings")
        result[key] = item
    return result


def _filter_mapping(value: Any) -> Dict[str, FrozenSet[str]]:
    if not isinstance(value, Mapping) or not value:
        raise ConfigValidationError("filter_fields must be a non-empty object")
    result: Dict[str, FrozenSet[str]] = {}
    values = cast(Mapping[Any, Any], value)
    for key, raw_fields in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigValidationError("filter_fields keys must be non-empty strings")
        if not isinstance(raw_fields, (list, tuple, set, frozenset)):
            raise ConfigValidationError("filter_fields values must be arrays")
        fields = cast(Any, raw_fields)
        if any(not isinstance(field, str) or not field.strip() for field in fields):
            raise ConfigValidationError("filter_fields values must contain strings")
        result[key] = frozenset(cast(Tuple[str, ...], tuple(fields)))
    return result
