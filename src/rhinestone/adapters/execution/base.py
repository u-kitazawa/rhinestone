"""Public base class for execution adapters."""

from abc import ABC, abstractmethod
from typing import Any

from ...models import AccessPlan
from ...security import DestinationPolicy

__all__ = ["ExecutionAdapter"]


class ExecutionAdapter(ABC):
    """Base for adapters that translate a selected ``AccessPlan`` to an OSS call."""

    name: str
    """Stable dependency and selection name."""

    priority: int
    """Deterministic selection priority."""

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        self._destination_policy = (
            destination_policy or DestinationPolicy.unrestricted()
        )

    @abstractmethod
    def supports(self, plan: AccessPlan) -> bool:
        """Whether this adapter can open the already selected plan."""

    @abstractmethod
    def open(
        self,
        plan: AccessPlan,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Delegate the already selected plan to the supplied runtime."""

    def authorize(
        self,
        plan: AccessPlan,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        """Authorize a resource before resolving its user-owned runtime."""
        (destination_policy or self._destination_policy).authorize(plan.uri)
