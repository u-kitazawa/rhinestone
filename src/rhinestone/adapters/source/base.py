"""Public base class for provider source adapters."""

import json
from abc import ABC, abstractmethod
from importlib import resources
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union, cast

from jsonschema import Draft202012Validator, ValidationError

from ...errors import (
    ConfigValidationError,
    ProviderMetadataError,
    ProviderResponseError,
)
from ...models import Config, Source

JsonObject = Mapping[str, Any]
JsonGetter = Callable[[str, Mapping[str, Any]], Any]
AuthenticatedJsonGetter = Callable[[str, Mapping[str, Any], Mapping[str, str]], Any]
JsonTransport = Union[JsonGetter, AuthenticatedJsonGetter]

__all__ = ["AuthenticatedJsonGetter", "JsonGetter", "JsonObject", "ProviderAdapter"]


class ProviderAdapter(ABC):
    """Base for adapters that translate provider metadata into a ``Source``.

    Subclasses own provider-specific configuration and response interpretation.
    The base class only standardizes validation and the injected JSON transport.
    Search is deliberately optional and is therefore not part of this abstract
    contract.
    """

    source_type = ""

    def __init__(
        self,
        get_json: JsonTransport,
        endpoint: Optional[str] = None,
        api_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        token_scheme: str = "Bearer",
    ) -> None:
        self._get_json = get_json
        self._endpoint = self._normalize_endpoint(endpoint) if endpoint else None
        if api_token is not None and api_key is not None:
            raise ConfigValidationError(
                "Configure either api_token or api_key, not both"
            )
        if api_token is not None and not api_token:
            raise ConfigValidationError("api_token must be non-empty")
        if api_key is not None and (not api_key or not api_key_header):
            raise ConfigValidationError("api_key and api_key_header must be non-empty")
        self._headers: Dict[str, str] = {}
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
        if config.source_type != self.source_type:
            raise ConfigValidationError(
                f"Expected source_type {self.source_type!r}; got {config.source_type!r}"
            )
        schema = self.config_schema()
        if schema is not None:
            try:
                validator: Any = Draft202012Validator(schema)
                validator.validate(_json_value(config.settings))
            except ValidationError as error:
                location = ".".join(str(item) for item in error.absolute_path)
                detail = f"{location}: " if location else ""
                raise ConfigValidationError(detail + error.message) from None
        return config.settings

    def config_schema(self) -> Optional[Mapping[str, Any]]:
        """Return this built-in adapter's JSON Schema, if it provides one."""
        try:
            text = (
                resources.files(type(self).__module__)
                .joinpath("schema.json")
                .read_text()
            )
        except (FileNotFoundError, ModuleNotFoundError, TypeError):
            return None
        return cast(Mapping[str, Any], json.loads(text))

    def _endpoint_from(
        self, settings: Mapping[str, Any], default: Optional[str] = None
    ) -> str:
        value = settings.get("endpoint", self._endpoint or default)
        if not isinstance(value, str) or not value.strip():
            raise ConfigValidationError("endpoint must be a non-empty string")
        return self._normalize_endpoint(value)

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        return endpoint.rstrip("/")

    @staticmethod
    def _required_string(settings: Mapping[str, Any], name: str) -> str:
        value = settings.get(name)
        if not isinstance(value, str) or not value:
            raise ConfigValidationError(f"{name} must be a non-empty string")
        return value

    def _request(self, url: str, params: Mapping[str, Any]) -> JsonObject:
        try:
            getter = cast(Any, self._get_json)
            if self._headers:
                response = getter(url, params, dict(self._headers))
            else:
                response = getter(url, params)
        except Exception as error:
            raise ProviderMetadataError(
                f"Provider metadata request failed for {url!r}"
            ) from error
        if not isinstance(response, Mapping):
            raise ProviderResponseError("Provider response root must be an object")
        return cast(JsonObject, response)

    @staticmethod
    def _object(value: Any, context: str) -> JsonObject:
        if not isinstance(value, Mapping):
            raise ProviderResponseError(f"{context} must be an object")
        return cast(JsonObject, value)

    @staticmethod
    def _objects(value: Any, context: str) -> Tuple[JsonObject, ...]:
        if isinstance(value, Mapping):
            return (cast(JsonObject, value),)
        if not isinstance(value, list):
            raise ProviderResponseError(f"{context} must be an object or array")
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
