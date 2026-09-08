"""Public base class for execution adapters."""

from abc import ABC, abstractmethod
from typing import Any, FrozenSet

from ...models import Resource
from ...security import DestinationPolicy

__all__ = ["ExecutionAdapter"]


class ExecutionAdapter(ABC):
    """Base for adapters that translate a selected ``Resource`` to an OSS call."""

    name: str
    """Stable dependency and selection name."""

    priority: int
    """Deterministic selection priority."""

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        self._destination_policy = (
            destination_policy or DestinationPolicy.unrestricted()
        )

    @abstractmethod
    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        """Whether this adapter can open the already selected resource."""

    @abstractmethod
    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Delegate the already selected resource to the supplied runtime."""
