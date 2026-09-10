"""Rasterio execution adapter."""

from typing import Any, FrozenSet

from ....errors import DestinationNotAllowedError, ResourceAccessError
from ....models import Resource
from ....security import DestinationPolicy
from .._locator import authorize_runtime_locator
from ..base import ExecutionAdapter


class RasterioAdapter(ExecutionAdapter):
    """Delegate raster Resources to a supplied Rasterio module."""

    name = "rasterio"
    priority = 15
    _formats = frozenset({"cog", "geotiff"})

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return (
            resource.format or ""
        ).lower() in self._formats and self.name in dependencies

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        policy = destination_policy or self._destination_policy
        authorize_runtime_locator(resource.uri, policy)
        driver = self._driver(resource, policy)
        try:
            return (
                runtime.open(resource.uri, driver=driver)
                if driver is not None
                else runtime.open(resource.uri)
            )
        except Exception as error:
            raise ResourceAccessError(
                f"Rasterio could not open {resource.uri!r}"
            ) from error

    def authorize(
        self,
        resource: Resource,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        policy = destination_policy or self._destination_policy
        authorize_runtime_locator(resource.uri, policy)
        self._driver(resource, policy)

    @staticmethod
    def _driver(resource: Resource, policy: DestinationPolicy) -> str | None:
        if policy.level != "strict":
            return None
        if (resource.format or "").lower() not in RasterioAdapter._formats:
            raise DestinationNotAllowedError(
                "Rasterio strict policy does not allow this dataset driver"
            )
        return "GTiff"
