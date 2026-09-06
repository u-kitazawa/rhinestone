"""Internal adapter and user-owned dependency registries."""

from typing import Any, Callable, Dict, FrozenSet, Iterable, Mapping, Tuple

from .errors import (
    AdapterRegistrationError,
    CredentialLoadError,
    CredentialUnavailableError,
    DependencyUnavailableError,
    ExecutionAdapterUnavailableError,
    UnsupportedSourceError,
)
from .models import DependencyValue


class CredentialRegistry:
    """Resolve user-owned secrets on demand, without caching them."""

    def __init__(self, factories: Mapping[str, Callable[[], str]]) -> None:
        self._factories = dict(factories)

    def get(self, name: str) -> str:
        if name not in self._factories:
            raise CredentialUnavailableError("Credential is not configured")
        try:
            secret: Any = self._factories[name]()
        except Exception:
            raise CredentialLoadError("Credential factory failed") from None
        if not isinstance(secret, str) or not secret:
            raise CredentialLoadError("Credential must be a non-empty string")
        return secret


class DependencyRegistry:
    """Resolve injected runtime objects, supporting optional lazy factories."""

    def __init__(self, values: Mapping[str, DependencyValue]) -> None:
        self._values = dict(values)
        self._instances: Dict[str, Any] = {}

    def get(self, name: str) -> Any:
        if name in self._instances:
            return self._instances[name]
        try:
            value = self._values[name]
        except KeyError:
            raise DependencyUnavailableError(
                f"Runtime dependency {name!r} is not configured"
            )
        try:
            instance = value() if callable(value) else value
        except Exception as error:
            raise DependencyUnavailableError(
                f"Runtime dependency {name!r} could not be loaded"
            ) from error
        self._instances[name] = instance
        return instance

    @property
    def available(self) -> FrozenSet[str]:
        return frozenset(self._values)


class AdapterRegistry:
    def __init__(
        self, source_adapters: Iterable[Any], execution_adapters: Iterable[Any]
    ) -> None:
        self._sources = self._index(source_adapters, "source_id")
        self._executions = self._index(execution_adapters, "name")

    @staticmethod
    def _index(adapters: Iterable[Any], identity_attribute: str) -> Dict[str, Any]:
        indexed: Dict[str, Any] = {}
        for adapter in adapters:
            identity = getattr(adapter, identity_attribute)
            if identity in indexed:
                raise AdapterRegistrationError(
                    f"Adapter {identity!r} is registered more than once"
                )
            indexed[identity] = adapter
        return indexed

    def source(self, source_id: str) -> Any:
        try:
            return self._sources[source_id]
        except KeyError:
            raise UnsupportedSourceError(f"Source {source_id!r} is not configured")

    def execution(self, name: str) -> Any:
        try:
            return self._executions[name]
        except KeyError:
            raise ExecutionAdapterUnavailableError(
                f"Execution adapter {name!r} is not registered"
            )

    @property
    def execution_adapters(self) -> Tuple[Any, ...]:
        return tuple(self._executions.values())
