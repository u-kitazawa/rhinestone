"""Selected JSON service requests delegated to a requests-compatible runtime."""

from typing import Any, Callable, FrozenSet, List, Mapping, Optional, Tuple, cast

from ..errors import ProviderResponseError, ResourceAccessError
from ..models import AccessPlan, Resource, ServiceQueryPlan
from ..registry import CredentialRegistry

RequestPreparer = Callable[
    [AccessPlan, CredentialRegistry], Tuple[Mapping[str, Any], Mapping[str, str]]
]


class JsonServiceAdapter:
    name = "json-service"
    priority = 10

    def __init__(
        self,
        prepare_request: RequestPreparer,
        service: str,
        credentials: Optional[CredentialRegistry] = None,
    ) -> None:
        self._prepare_request = prepare_request
        self._service = service
        self._credentials = credentials or CredentialRegistry({})

    def bind_credentials(self, credentials: CredentialRegistry) -> "JsonServiceAdapter":
        return JsonServiceAdapter(self._prepare_request, self._service, credentials)

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return (
            self.name in dependencies
            and isinstance(resource.access_plan, ServiceQueryPlan)
            and resource.media_type == "application/json"
            and resource.access_plan.options.get("service") == self._service
        )

    def open(self, resource: Resource, runtime: Any) -> Any:
        params, headers = self._prepare_request(resource.access_plan, self._credentials)
        try:
            response = runtime.get(
                resource.uri,
                params=params,
                headers=headers,
                timeout=30,
                allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                raise ResourceAccessError("Service redirects are not supported")
            response.raise_for_status()
        except Exception:
            # requests exceptions may include a URL containing the secret query.
            raise ResourceAccessError("JSON service request failed") from None
        try:
            data = response.json()
        except Exception:
            raise ProviderResponseError("Service returned invalid JSON") from None
        if resource.access_plan.options.get("response_type") == "array" and (
            not isinstance(data, list)
            or any(not isinstance(item, Mapping) for item in cast(List[Any], data))
        ):
            raise ProviderResponseError("Service must return an array of objects")
        return cast(Any, data)
