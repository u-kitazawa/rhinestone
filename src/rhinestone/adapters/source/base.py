"""Public base class for provider source adapters."""

import json
from abc import ABC, abstractmethod
from importlib import resources
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union, cast
from urllib.parse import quote

from jsonschema import Draft202012Validator, ValidationError

from ...errors import (
    ConfigValidationError,
    ProviderMetadataError,
    ProviderResponseError,
)
from ...models import Config, Source
from ...registry import CredentialRegistry
from ...security import DestinationPolicy

JsonObject = Mapping[str, Any]
JsonGetter = Callable[[str, Mapping[str, Any]], Any]
AuthenticatedJsonGetter = Callable[[str, Mapping[str, Any], Mapping[str, str]], Any]
JsonTransport = Union[JsonGetter, AuthenticatedJsonGetter]


class _CredentialHeaders(dict[str, str]):
    """Mark provider headers so the built-in transport rejects redirects."""

    _rhinestone_no_redirects = True


__all__ = ["AuthenticatedJsonGetter", "JsonGetter", "JsonObject", "ProviderAdapter"]


class ProviderAdapter(ABC):
    """Base for adapters that translate provider metadata into a ``Source``.

    Subclasses own provider-specific configuration and response interpretation.
    The base class only standardizes validation and the injected JSON transport.
    Search is deliberately optional and is therefore not part of this abstract
    contract.
    """

    adapter_type = ""

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = None,
        api_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        token_scheme: str = "Bearer",
        credential: Optional[str] = None,
        credential_header: Optional[str] = None,
        credential_scheme: Optional[str] = None,
        credentials: Optional[CredentialRegistry] = None,
        destination_policy: Optional[DestinationPolicy] = None,
        provider_id: Optional[str] = None,
    ) -> None:
        self._get_json = get_json
        self._endpoint = self._normalize_endpoint(endpoint) if endpoint else None
        if credential is not None and not credential:
            raise ConfigValidationError("credential must be a non-empty string")
        if credential is not None and (api_token is not None or api_key is not None):
            raise ConfigValidationError(
                "Configure either credential or a direct API secret"
            )
        self._credential_name = credential
        self._provider_id = provider_id
        self._credentials = credentials or CredentialRegistry({})
        self._destination_policy = (
            destination_policy or DestinationPolicy.unrestricted()
        )
        if api_token is not None and api_key is not None:
            raise ConfigValidationError(
                "Configure either api_token or api_key, not both"
            )
        if api_token is not None and not api_token:
            raise ConfigValidationError("api_token must be non-empty")
        if api_key is not None and (not api_key or not api_key_header):
            raise ConfigValidationError("api_key and api_key_header must be non-empty")
        self._headers: Dict[str, str] = {}
        self._credential_header = (
            "Authorization" if credential_header is None else credential_header
        )
        self._credential_prefix = ""
        if not cast(object, self._credential_header) or not isinstance(
            cast(object, self._credential_header), str
        ):
            raise ConfigValidationError("credential_header must be non-empty")
        if credential is not None:
            scheme = token_scheme if credential_scheme is None else credential_scheme
            if not isinstance(cast(object, scheme), str):
                raise ConfigValidationError("credential_scheme must be a string")
            self._credential_prefix = f"{scheme} " if scheme else ""
        if api_token is not None:
            self._headers["Authorization"] = (
                f"{token_scheme} {api_token}" if token_scheme else api_token
            )
        elif api_key is not None:
            self._headers[api_key_header] = api_key

    @abstractmethod
    def load(self, config: Config) -> Source:
        """Interpret a provider config and return its knowledge-preserving source."""

    def _config_settings(self, config: Config) -> Mapping[str, Any]:
        if config.source_id != self.adapter_type:
            raise ConfigValidationError(
                f"Expected adapter type {self.adapter_type!r}; got "
                f"{config.source_id!r}; construct Config with the adapter's "
                "source type"
            )
        schema = self.config_schema()
        if schema is not None:
            try:
                validator: Any = Draft202012Validator(schema)
                validator.validate(_json_value(config.settings))
            except ValidationError as error:
                location = ".".join(str(item) for item in error.absolute_path)
                detail = f"{location}: " if location else ""
                raise ConfigValidationError(
                    f"Invalid {self.adapter_type} configuration: {detail}"
                    f"{error.message}"
                ) from None
        return config.settings

    def config_schema(self) -> Optional[Mapping[str, Any]]:
        """Return this built-in adapter's JSON Schema, if it provides one."""
        module_name = type(self).__module__
        try:
            package_name = module_name.rpartition(".")[0] or module_name
            text = resources.files(package_name).joinpath("schema.json").read_text()
        except (FileNotFoundError, ModuleNotFoundError, TypeError):
            return None
        return cast(Mapping[str, Any], json.loads(text))

    def _endpoint_from(
        self, settings: Mapping[str, Any], default: Optional[str] = None
    ) -> str:
        if self._endpoint is not None:
            configured = settings.get("endpoint")
            if configured is not None:
                if not isinstance(configured, str) or not configured.strip():
                    raise ConfigValidationError(
                        "endpoint must be a non-empty string; provide the "
                        "provider API endpoint"
                    )
                if self._normalize_endpoint(configured) != self._endpoint:
                    raise ConfigValidationError(
                        "endpoint is managed by the SourceDefinition"
                    )
            return self._endpoint
        value = settings.get("endpoint", self._endpoint or default)
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError(
                "endpoint must be a non-empty string; provide the provider API endpoint"
            )
        return self._normalize_endpoint(value)

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        return endpoint.rstrip("/")

    @staticmethod
    def _encode_path_segment(value: str) -> str:
        """Encode one decoded logical identifier for use as a URL path segment."""
        if value in {".", ".."}:
            return value.replace(".", "%2E")
        return quote(value, safe="")

    @staticmethod
    def _required_string(settings: Mapping[str, Any], name: str) -> str:
        value = settings.get(name)
        if not isinstance(value, str) or not value:
            raise ConfigValidationError(
                f"{name} must be a non-empty string; provide this required "
                "configuration value"
            )
        return value

    def _request(self, url: str, params: Mapping[str, Any]) -> JsonObject:
        response, _ = self._request_with_uri(url, params)
        return response

    def _request_with_uri(
        self, url: str, params: Mapping[str, Any]
    ) -> Tuple[JsonObject, str]:
        credentialed = self._credential_name is not None or bool(self._headers)
        self._destination_policy.authorize(
            url,
            credentialed=credentialed,
            provider=self._provider_id,
            service=self.adapter_type,
            credential=self._credential_name,
        )
        headers: Dict[str, str] = dict(self._headers)
        if self._credential_name is not None:
            headers[self._credential_header] = (
                self._credential_prefix + self._credentials.get(self._credential_name)
            )
        if headers:
            headers = _CredentialHeaders(headers)
        try:
            getter = cast(Any, self._get_json)
            if headers:
                response = getter(url, params, headers)
            else:
                response = getter(url, params)
        except OSError as error:
            raise ProviderMetadataError(
                f"Provider metadata request failed for {url!r}"
            ) from error
        if not isinstance(response, Mapping):
            raise ProviderResponseError(
                "Provider response root must be an object; the decoded response "
                "did not match the provider contract"
            )
        response_uri = getattr(cast(Any, response), "response_uri", url)
        if not isinstance(response_uri, str) or not response_uri:
            response_uri = url
        return cast(JsonObject, response), response_uri

    @staticmethod
    def _object(value: Any, context: str) -> JsonObject:
        if not isinstance(value, Mapping):
            raise ProviderResponseError(
                f"{context} must be an object; provider response shape is invalid"
            )
        return cast(JsonObject, value)

    @staticmethod
    def _objects(value: Any, context: str) -> Tuple[JsonObject, ...]:
        if isinstance(value, Mapping):
            return (cast(JsonObject, value),)
        if not isinstance(value, list):
            raise ProviderResponseError(
                f"{context} must be an object or array; provider response shape "
                "is invalid"
            )
        values = cast(List[Any], value)
        return tuple(ProviderAdapter._object(item, context) for item in values)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return {key: _json_value(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        items = cast(Tuple[Any, ...], value)
        return [_json_value(item) for item in items]
    return value
