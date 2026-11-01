"""Deterministic selection of runtime adapters."""

from collections.abc import Iterable, Mapping
from typing import Protocol, cast, runtime_checkable

from .adapters.contracts import RuntimeAdapter
from .errors import AdapterRegistrationError, RuntimeAdapterUnavailableError
from .models import AccessPlan, LibraryName
from .security import DestinationPolicy


@runtime_checkable
class AuthorizingRuntimeAdapter(Protocol):
    """Optional execution capability for pre-runtime authorization."""

    def authorize(
        self,
        plan: AccessPlan,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        """Authorize access before resolving a user-owned runtime."""
        ...


class RuntimeAdapterSelector:
    """Select the highest-priority compatible runtime adapter."""

    def __init__(
        self, adapters: Iterable[RuntimeAdapter] | Mapping[str, RuntimeAdapter]
    ) -> None:
        self._adapters: Mapping[str, RuntimeAdapter]
        if isinstance(adapters, Mapping):
            self._adapters = cast(Mapping[str, RuntimeAdapter], adapters)
        else:
            declared = tuple(adapters)
            self._adapters = {adapter.name: adapter for adapter in declared}
            if len(self._adapters) != len(declared):
                raise AdapterRegistrationError("Runtime adapter names must be unique")

    def select(
        self,
        plan: AccessPlan,
        requested: LibraryName | None = None,
    ) -> RuntimeAdapter:
        """Select an adapter for an AccessPlan and optional explicit library name.

        A requested library is never silently replaced by another adapter. If
        no library is requested, priority and name determine a deterministic
        choice among compatible adapters.
        """
        if requested is not None:
            # Identity is metadata. Check it before touching supports/priority,
            # which may require loading a selected installed package.
            adapter = self._adapters.get(requested)
            compatible = (
                [adapter] if adapter is not None and adapter.supports(plan) else []
            )
            if not compatible:
                raise RuntimeAdapterUnavailableError(
                    f"Runtime adapter {requested!r} is unavailable or "
                    "incompatible with the selected plan"
                )
        else:
            compatible = [
                adapter for adapter in self._adapters.values() if adapter.supports(plan)
            ]
        if not compatible:
            raise RuntimeAdapterUnavailableError(
                "No runtime adapter supports the selected plan with the "
                "registered adapters"
            )
        return max(
            compatible,
            key=lambda adapter: (adapter.priority, adapter.name),
        )
