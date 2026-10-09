"""Rasterio execution adapter."""

from typing import Any

from ....errors import ResourceAccessError
from ....models import AccessPlan
from ....representations import canonical_format
from ....security import DestinationPolicy
from ..base import ExecutionAdapter


class RasterioAdapter(ExecutionAdapter):
    """Delegate raster AccessPlans to a supplied Rasterio module."""

    name = "rasterio"
    priority = 15
    _formats = frozenset({"cog", "geotiff"})

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, plan: AccessPlan) -> bool:
        """Return whether Rasterio and the AccessPlan's raster format are compatible."""
        return canonical_format(plan.format) in self._formats

    def open(
        self,
        plan: AccessPlan,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Open the selected raster AccessPlan with ``runtime.open``."""
        try:
            return runtime.open(plan.uri)
        except Exception as error:
            raise ResourceAccessError(
                f"Rasterio could not open {plan.uri!r}"
            ) from error
