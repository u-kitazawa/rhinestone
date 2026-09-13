"""Built-in adapters that delegate selected Resources to user-owned runtimes."""

from typing import Any, FrozenSet, List, Mapping, cast
from urllib.parse import urlparse

from ....errors import ResourceAccessError
from ....models import FileAccessPlan, Resource
from ....security import DestinationPolicy
from .._resource import resource_attributes
from ..base import ExecutionAdapter
from .tile import tile_xml as build_tile_xml


class GdalAdapter(ExecutionAdapter):
    """Translate Resources into calls understood by a supplied GDAL module."""

    name = "gdal"
    priority = 20
    _formats = frozenset(
        {"shapefile", "geotiff", "cog", "netcdf", "wms", "gml", "kml", "citygml"}
    )

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        """Return whether GDAL and the Resource's format are compatible."""
        tile = resource.access_plan.options.get("tile")
        return self.name in dependencies and (
            (resource.format or "").lower() in self._formats
            or (
                isinstance(tile, Mapping)
                and cast(Mapping[str, Any], tile).get("scheme") == "xyz"
            )
        )

    def open(
        self,
        resource: Resource,
        runtime: Any,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> Any:
        """Open the selected Resource with ``runtime.OpenEx``."""
        uri = self._runtime_uri(resource)
        attributes = resource_attributes(resource)
        options: List[str] = []
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options.append("ENCODING=" + encoding.upper())
        try:
            runtime_options: dict[str, Any] = {"open_options": tuple(options)}
            result = runtime.OpenEx(uri, **runtime_options)
            if result is None:
                raise ResourceAccessError(
                    "GDAL returned no dataset; verify the selected Resource and "
                    "GDAL-supported format"
                )
            return result
        except Exception as error:
            raise ResourceAccessError(
                f"GDAL could not open {resource.uri!r}"
            ) from error

    @staticmethod
    def _runtime_uri(resource: Resource) -> str:
        attributes = resource_attributes(resource)
        uri = resource.uri
        tile = resource.access_plan.options.get("tile")
        if tile is not None:
            if not isinstance(tile, Mapping):
                raise ResourceAccessError(
                    "GDAL tile options must be an object; provide explicit tile "
                    "configuration in AccessPlan.options"
                )
            tile = cast(Mapping[str, Any], tile)
            tile_url = tile.get("url")
            if not isinstance(tile_url, str):
                raise ResourceAccessError(
                    "GDAL tile URL must be a string; provide a valid tile endpoint"
                )
            uri = build_tile_xml(tile)
        archive = attributes.get("archive")
        if isinstance(resource.access_plan, FileAccessPlan):
            archive = resource.access_plan.archive or archive
        if archive == "zip":
            uri = (
                "/vsizip//vsicurl/" + uri
                if urlparse(uri).scheme.casefold() in {"http", "https"}
                else "/vsizip/" + uri
            )
            member = resource.access_plan.options.get("entry_point")
            if member:
                uri += "/" + member
        return uri

    @staticmethod
    def tile_xml(tile: Mapping[str, Any]) -> str:
        """Build GDAL WMS/XYZ tile XML from explicit tile options."""
        return build_tile_xml(tile)
