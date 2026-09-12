"""Internal adapter and user-owned dependency registries."""

from typing import Any, Callable, Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

from .errors import (
    AdapterRegistrationError,
    CredentialLoadError,
    CredentialUnavailableError,
    DependencyUnavailableError,
    ExecutionAdapterUnavailableError,
    UnsupportedSourceError,
)
from .models import DependencyValue, RuntimeFactory


class CredentialRegistry:
    """Resolve logical credentials on demand without retaining their secrets.

    Credential factories are called for each request that needs the credential.
    Only the logical name is used in diagnostics; the returned secret is never
    included in an exception message or public model.
    """

    def __init__(self, factories: Mapping[str, Callable[[], str]]) -> None:
        self._factories = dict(factories)

    def get(self, name: str) -> str:
        if name not in self._factories:
            raise CredentialUnavailableError(
                f"Credential {name!r} is not configured; register a factory in "
                "configure(credentials=...)"
            )
        try:
            secret: Any = self._factories[name]()
        except Exception:
            raise CredentialLoadError(
                f"Credential factory for {name!r} failed; the secret was not "
                "included in this error"
            ) from None
        if not isinstance(secret, str) or not secret:
            raise CredentialLoadError(
                f"Credential factory for {name!r} must return a non-empty string"
            )
        return secret


class DependencyRegistry:
    """Resolve injected runtime objects with optional lazy factories.

    A ``RuntimeFactory`` is evaluated once per shared registry cache. Bare
    callable runtime objects are treated as runtime instances and are not
    invoked implicitly.
    """

    def __init__(
        self,
        values: Mapping[str, DependencyValue],
        instances: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._values = dict(values)
        self._instances = instances if instances is not None else {}

    def scoped(self, names: Iterable[str]) -> "DependencyRegistry":
        """Return a view with the same lazy-instance cache and limited names."""
        allowed = frozenset(names)
        return DependencyRegistry(
            {name: value for name, value in self._values.items() if name in allowed},
            self._instances,
        )

    def get(self, name: str) -> Any:
        """Return one runtime, loading and caching a declared factory if needed.

        Raises:
            DependencyUnavailableError: If the name is missing or its factory
                cannot load the runtime. The original factory error is chained.
        """
        if name in self._instances:
            return self._instances[name]
        try:
            value = self._values[name]
        except KeyError:
            raise DependencyUnavailableError(
                f"Runtime dependency {name!r} is not configured; inject it in "
                "configure(dependencies=...)"
            )
        try:
            instance = value.factory() if isinstance(value, RuntimeFactory) else value
        except Exception as error:
            raise DependencyUnavailableError(
                f"Runtime dependency {name!r} could not be loaded"
            ) from error
        self._instances[name] = instance
        return instance

    @property
    def available(self) -> FrozenSet[str]:
        """Return names of dependencies declared in this registry scope."""
        return frozenset(self._values)


class AdapterRegistry:
    """Index configured Source and Execution Adapters by their public identity."""

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
                    f"Adapter {identity!r} is registered more than once; each "
                    "adapter identity must be unique"
                )
            indexed[identity] = adapter
        return indexed

    def source(self, source_id: str) -> Any:
        """Return the configured Source Adapter for ``source_id``."""
        try:
            return self._sources[source_id]
        except KeyError:
            raise UnsupportedSourceError(
                f"Source {source_id!r} is not configured; add it to the "
                "application Catalog or sources iterable"
            )

    def execution(self, name: str) -> Any:
        """Return the registered Execution Adapter named ``name``."""
        try:
            return self._executions[name]
        except KeyError:
            raise ExecutionAdapterUnavailableError(
                f"Execution adapter {name!r} is not registered; provide a "
                "matching ExecutionAdapterDefinition"
            )

    @property
    def execution_adapters(self) -> Tuple[Any, ...]:
        """Return registered Execution Adapters in deterministic order."""
        return tuple(self._executions.values())
