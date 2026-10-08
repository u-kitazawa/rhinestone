"""Deterministic selection of execution adapters."""

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from .adapters.contracts import ExecutionAdapter
from .errors import ExecutionAdapterUnavailableError
from .models import AccessPlan, LibraryName
from .security import DestinationPolicy


@runtime_checkable
class AuthorizingExecutionAdapter(Protocol):
    """Optional execution capability for pre-runtime authorization."""

    def authorize(
        self,
        plan: AccessPlan,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        """Authorize access before resolving a user-owned runtime."""
        ...


class ExecutionAdapterSelector:
    """Select the highest-priority compatible execution adapter."""

    def __init__(self, adapters: Iterable[ExecutionAdapter]) -> None:
        self._adapters = tuple(adapters)

    def select(
        self,
        plan: AccessPlan,
        requested: LibraryName | None = None,
    ) -> ExecutionAdapter:
        """Select an adapter for an AccessPlan and optional explicit library name.

        A requested library is never silently replaced by another adapter. If
        no library is requested, priority and name determine a deterministic
        choice among compatible adapters.
        """
        compatible = [adapter for adapter in self._adapters if adapter.supports(plan)]
        if requested is not None:
            compatible = [
                adapter for adapter in compatible if adapter.name == requested
            ]
            if not compatible:
                raise ExecutionAdapterUnavailableError(
                    f"Execution adapter {requested!r} is unavailable or "
                    "incompatible with the selected plan"
                )
        if not compatible:
            raise ExecutionAdapterUnavailableError(
                "No execution adapter supports the selected plan with the "
                "registered adapters"
            )
        return max(
            compatible,
            key=lambda adapter: (adapter.priority, adapter.name),
        )
