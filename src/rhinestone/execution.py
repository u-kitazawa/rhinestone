"""Deterministic selection of execution adapters."""

from typing import Any, FrozenSet, Iterable, Optional

from .errors import ExecutionAdapterUnavailableError
from .models import LibraryName


class ExecutionAdapterSelector:
    """Select the highest-priority compatible execution adapter."""

    def __init__(self, adapters: Iterable[Any]) -> None:
        self._adapters = tuple(adapters)

    def select(
        self,
        resource: Any,
        dependencies: FrozenSet[str],
        requested: Optional[LibraryName] = None,
    ) -> Any:
        """Select an adapter for a Resource and optional explicit library name.

        A requested library is never silently replaced by another adapter. If
        no library is requested, priority and name determine a deterministic
        choice among compatible adapters.
        """
        compatible = [
            adapter
            for adapter in self._adapters
            if adapter.supports(resource, dependencies)
        ]
        if requested is not None:
            compatible = [
                adapter for adapter in compatible if adapter.name == requested
            ]
            if not compatible:
                raise ExecutionAdapterUnavailableError(
                    f"Execution adapter {requested!r} is unavailable or "
                    "incompatible with the selected resource or injected "
                    "runtime"
                )
        if not compatible:
            raise ExecutionAdapterUnavailableError(
                "No execution adapter supports the selected resource with the "
                "currently injected runtimes"
            )
        return max(
            compatible,
            key=lambda adapter: (adapter.priority, adapter.name),
        )
