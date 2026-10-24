"""Internal adapter and user-owned dependency registries."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from threading import RLock
from typing import Any, TypeVar, cast

from ._adapter_contracts import RegisteredProviderAdapter
from .adapters.contracts import RuntimeAdapter
from .errors import (
    AdapterRegistrationError,
    CredentialLoadError,
    CredentialUnavailableError,
    DependencyUnavailableError,
    RuntimeAdapterUnavailableError,
    UnsupportedProviderError,
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
        instances: dict[str, Any] | None = None,
        initialization_locks: dict[str, RLock] | None = None,
        lock: RLock | None = None,
    ) -> None:
        self._lock = lock if lock is not None else RLock()
        self._dependency_values = dict(values)
        self._loaded_dependencies = instances if instances is not None else {}
        self._initialization_locks = (
            initialization_locks if initialization_locks is not None else {}
        )

    def scoped(self, names: Iterable[str]) -> DependencyRegistry:
        """Return a view with the same lazy-instance cache and limited names."""
        allowed = frozenset(names)
        return DependencyRegistry(
            {
                name: value
                for name, value in self._dependency_values.items()
                if name in allowed
            },
            self._loaded_dependencies,
            self._initialization_locks,
            self._lock,
        )

    def get(self, name: str) -> Any:
        """Return one runtime, loading and caching a declared factory if needed.

        Raises:
            DependencyUnavailableError: If the name is missing or its factory
                cannot load the runtime. The original factory error is chained.
        """
        with self._lock:
            if name in self._loaded_dependencies:
                return self._loaded_dependencies[name]
            try:
                value = self._dependency_values[name]
            except KeyError:
                raise DependencyUnavailableError(
                    f"Runtime dependency {name!r} is not configured; inject it in "
                    "configure(dependencies=...)"
                )
            initialization_lock = self._initialization_locks.setdefault(name, RLock())

        with initialization_lock:
            with self._lock:
                if name in self._loaded_dependencies:
                    return self._loaded_dependencies[name]
            try:
                instance = (
                    value.factory() if isinstance(value, RuntimeFactory) else value
                )
            except Exception as error:
                raise DependencyUnavailableError(
                    f"Runtime dependency {name!r} could not be loaded"
                ) from error
            with self._lock:
                self._loaded_dependencies[name] = instance
            return instance

    @property
    def available(self) -> frozenset[str]:
        """Return names of dependencies declared in this registry scope."""
        return frozenset(self._dependency_values)


_Adapter = TypeVar("_Adapter")


class AdapterRegistry:
    """Index configured Provider and Runtime Adapters by their public identity."""

    def __init__(
        self,
        provider_adapters: Iterable[RegisteredProviderAdapter],
        runtime_adapters: Iterable[RuntimeAdapter] | Mapping[str, RuntimeAdapter],
    ) -> None:
        self._provider_adapters = self._index(
            provider_adapters, lambda adapter: adapter.source_id
        )
        self._runtime_adapters: Mapping[str, RuntimeAdapter] = (
            cast(Mapping[str, RuntimeAdapter], runtime_adapters)
            if isinstance(runtime_adapters, Mapping)
            else self._index(runtime_adapters, lambda adapter: adapter.name)
        )

    @staticmethod
    def _index(
        adapters: Iterable[_Adapter], identity: Callable[[_Adapter], str]
    ) -> dict[str, _Adapter]:
        indexed: dict[str, _Adapter] = {}
        for adapter in adapters:
            adapter_identity = identity(adapter)
            if adapter_identity in indexed:
                raise AdapterRegistrationError(
                    f"Adapter {adapter_identity!r} is registered more than once; each "
                    "adapter identity must be unique"
                )
            indexed[adapter_identity] = adapter
        return indexed

    def provider(self, source_id: str) -> RegisteredProviderAdapter:
        """Return the configured Provider Adapter for ``source_id``."""
        try:
            return self._provider_adapters[source_id]
        except KeyError:
            raise UnsupportedProviderError(
                f"Source {source_id!r} is not configured; add it to the "
                "application Catalog or sources iterable"
            )

    def runtime(self, name: str) -> RuntimeAdapter:
        """Return the registered Runtime Adapter named ``name``."""
        try:
            return self._runtime_adapters[name]
        except KeyError:
            raise RuntimeAdapterUnavailableError(
                f"Runtime adapter {name!r} is not registered; provide a "
                "matching RuntimeAdapterDefinition"
            )

    @property
    def runtime_adapters(self) -> Mapping[str, RuntimeAdapter]:
        """Expose adapter identities without instantiating unused installed ones."""
        return self._runtime_adapters
