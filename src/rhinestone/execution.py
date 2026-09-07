"""Deterministic selection of execution adapters."""

from typing import Any, FrozenSet, Iterable, Optional

from .errors import ExecutionAdapterUnavailableError
from .models import LibraryName


class ExecutionAdapterSelector:
    def __init__(self, adapters: Iterable[Any]) -> None:
        self._adapters = tuple(adapters)

    def select(
        self,
        resource: Any,
        dependencies: FrozenSet[str],
        requested: Optional[LibraryName] = None,
    ) -> Any:
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
                    f"Execution adapter {requested!r} is unavailable or incompatible"
                )
        if not compatible:
            raise ExecutionAdapterUnavailableError(
                "No execution adapter supports the selected resource"
            )
        return max(
            compatible,
            key=lambda adapter: (adapter.priority, adapter.name),
        )
