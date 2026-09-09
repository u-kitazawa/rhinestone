"""Rasterio execution adapter."""

from typing import Any, FrozenSet

from ....errors import ResourceAccessError
from ....models import Resource
from ..base import ExecutionAdapter


class RasterioAdapter(ExecutionAdapter):
    """Delegate raster Resources to a supplied Rasterio module."""

    name = "rasterio"
    priority = 15
    _formats = frozenset({"cog", "geotiff"})

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return (
            resource.format or ""
        ).lower() in self._formats and self.name in dependencies

    def open(self, resource: Resource, runtime: Any) -> Any:
        try:
            return runtime.open(resource.uri)
        except Exception as error:
            raise ResourceAccessError(
                f"Rasterio could not open {resource.uri!r}"
            ) from error
