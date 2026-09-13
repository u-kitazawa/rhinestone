"""Rasterio execution adapter."""

from typing import Any, FrozenSet

from ....errors import ResourceAccessError
from ....models import Resource
from ....representations import canonical_format
from ....security import DestinationPolicy
from ..base import ExecutionAdapter


class RasterioAdapter(ExecutionAdapter):
    """Delegate raster Resources to a supplied Rasterio module."""

    name = "rasterio"
    priority = 15
    _formats = frozenset({"cog", "geotiff"})

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        """Return whether Rasterio and the Resource's raster format are compatible."""
        return (
            canonical_format(resource.format) in self._formats
            and self.name in dependencies
        )

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Open the selected raster Resource with ``runtime.open``."""
        try:
            return runtime.open(resource.uri)
        except Exception as error:
            raise ResourceAccessError(
                f"Rasterio could not open {resource.uri!r}"
            ) from error
