"""Installed adapter uses the caller's Runtime object without importing one."""

from typing import Any

from rhinestone.adapters.contracts import (
    ExecutionAdapterContext,
    ExecutionAdapterDefinition,
)
from rhinestone.models import AccessPlan
from rhinestone.security import DestinationPolicy

calls: list[str] = []


class InstalledRuntimeAdapter:
    name = "installed-runtime"
    priority = 30

    def supports(self, plan: AccessPlan) -> bool:
        return plan.kind == "file" and plan.format == "geotiff"

    def open(
        self,
        plan: AccessPlan,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> object:
        calls.append("open")
        return runtime.read(plan.uri)


def factory(context: ExecutionAdapterContext) -> InstalledRuntimeAdapter:
    calls.append("factory")
    return InstalledRuntimeAdapter()


definition = ExecutionAdapterDefinition("installed-runtime", factory)
