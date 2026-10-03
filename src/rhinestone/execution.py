"""Deterministic selection of execution adapters."""

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from .adapters.contracts import ExecutionAdapter
from .errors import ExecutionAdapterUnavailableError
from .models import LibraryName, Resource
from .security import DestinationPolicy


@runtime_checkable
class AuthorizingExecutionAdapter(Protocol):
    """Optional execution capability for pre-runtime authorization."""

    def authorize(
        self,
        resource: Resource,
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
        resource: Resource,
        requested: LibraryName | None = None,
    ) -> ExecutionAdapter:
        """Select an adapter for a Resource and optional explicit library name.

        A requested library is never silently replaced by another adapter. If
        no library is requested, priority and name determine a deterministic
        choice among compatible adapters.
        """
        compatible = [
            adapter for adapter in self._adapters if adapter.supports(resource)
        ]
        if requested is not None:
            compatible = [
                adapter for adapter in compatible if adapter.name == requested
            ]
            if not compatible:
                raise ExecutionAdapterUnavailableError(
                    f"Execution adapter {requested!r} is unavailable or "
                    "incompatible with the selected resource"
                )
        if not compatible:
            raise ExecutionAdapterUnavailableError(
                "No execution adapter supports the selected resource with the "
                "registered adapters"
            )
        return max(
            compatible,
            key=lambda adapter: (adapter.priority, adapter.name),
        )
