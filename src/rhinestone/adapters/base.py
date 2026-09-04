"""Public base class for provider source adapters."""

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Mapping, Optional, Tuple, cast

from ..errors import ConfigValidationError, ProviderMetadataError, ProviderResponseError
from ..models import Config, Source

JsonObject = Mapping[str, Any]
JsonGetter = Callable[[str, Mapping[str, Any]], Any]

__all__ = ["JsonGetter", "JsonObject", "ProviderAdapter"]


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
        get_json: JsonGetter,
        endpoint: Optional[str] = None,
    ) -> None:
        self._get_json = get_json
        self._endpoint = self._normalize_endpoint(endpoint) if endpoint else None

    @abstractmethod
    def load(self, config: Config) -> Source:
        """Interpret a provider config and return its knowledge-preserving source."""

    def _config_settings(self, config: Config) -> Mapping[str, Any]:
        if config.source_type != self.source_type:
            raise ConfigValidationError(
                f"Expected source_type {self.source_type!r}; got {config.source_type!r}"
            )
        return config.settings

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
            response = self._get_json(url, params)
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
