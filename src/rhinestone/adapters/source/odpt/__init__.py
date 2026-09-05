"""ODPT v4 service knowledge; data requests are executed only by open()."""

from typing import Any, Dict, Mapping, Tuple, cast

from ....errors import ConfigValidationError
from ....models import AccessPlan, Config, ResourceCandidate, Source
from ....registry import CredentialRegistry
from .._knowledge import source, string
from ..base import ProviderAdapter

_ENDPOINT = "https://api.odpt.org/api/v4/"
_TYPES = {"station": "odpt:Station", "railway": "odpt:Railway", "train": "odpt:Train"}
_FILTERS = {
    "station": frozenset({"owl:sameAs", "dc:title", "odpt:operator", "odpt:railway"}),
    "railway": frozenset({"owl:sameAs", "dc:title", "odpt:operator"}),
    "train": frozenset(
        {"owl:sameAs", "odpt:operator", "odpt:railway", "odpt:trainNumber"}
    ),
}


class OdptAdapter(ProviderAdapter):
    source_type = "odpt"

    def __init__(self) -> None:
        super().__init__(get_json=lambda url, params: None)

    def load(self, config: Config) -> Source:
        settings = self._config_settings(config)
        if set(settings) - {"dataset", "credential", "filters"}:
            raise ConfigValidationError("Unknown ODPT setting; use official filters")
        dataset = string(settings, "dataset")
        if dataset not in _TYPES:
            raise ConfigValidationError("Expected station, railway or train")
        credential = string(settings, "credential")
        filters = settings.get("filters", {})
        if not isinstance(filters, Mapping):
            raise ConfigValidationError("filters must be an object")
        filters = cast(Mapping[str, Any], filters)
        if set(filters) - _FILTERS[dataset]:
            raise ConfigValidationError("Unsupported ODPT filter")
        for key in filters:
            string(filters, key)
        uri = _ENDPOINT + _TYPES[dataset]
        raw = {
            "resource_type": _TYPES[dataset],
            "filters": dict(filters),
            "spec_source": "https://developer.odpt.org/documents",
            "terms_url": "https://developer.odpt.org/terms/data_basic_license.html",
        }
        return source(
            self.source_type,
            _TYPES[dataset],
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
                            "service": "odpt",
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
        if (
            plan.kind != "service-query"
            or plan.options.get("service") != "odpt"
            or plan.uri not in {_ENDPOINT + name for name in _TYPES.values()}
        ):
            raise ConfigValidationError(
                "Credential destination is not an ODPT endpoint"
            )
        params: Dict[str, Any] = dict(plan.options["params"])
        params["acl:consumerKey"] = credentials.get(plan.options["credential"])
        return params, {}
