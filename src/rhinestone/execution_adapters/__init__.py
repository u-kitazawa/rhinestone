"""Built-in adapters that delegate selected Resources to user-owned runtimes."""

from typing import Any, Dict, FrozenSet, List, Mapping

from ..errors import ResourceAccessError
from ..models import FileAccessPlan, Resource

__all__ = ["GdalAdapter", "PyogrioAdapter", "RasterioAdapter"]


def _attributes(resource: Resource) -> Mapping[str, Any]:
    for candidate in resource.source.candidates:
        if candidate.uri == resource.uri:
            return candidate.attributes
    return {}


class GdalAdapter:
    """Translate Resources into calls understood by a supplied GDAL module."""

    name = "gdal"
    priority = 20
    _formats = frozenset({"shapefile", "geotiff", "cog", "netcdf", "wms"})

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return (
            resource.format or ""
        ).lower() in self._formats and self.name in dependencies

    def open(self, resource: Resource, runtime: Any) -> Any:
        attributes = _attributes(resource)
        uri = resource.uri
        archive = attributes.get("archive")
        if isinstance(resource.access_plan, FileAccessPlan):
            archive = resource.access_plan.archive or archive
        if archive == "zip":
            uri = (
                "/vsizip//vsicurl/" + uri
                if uri.startswith(("http://", "https://"))
                else "/vsizip/" + uri
            )
        options: List[str] = []
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options.append("ENCODING=" + encoding.upper())
        try:
            return runtime.OpenEx(uri, open_options=tuple(options))
        except Exception as error:
            raise ResourceAccessError(
                f"GDAL could not open {resource.uri!r}"
            ) from error


class RasterioAdapter:
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


class PyogrioAdapter:
    """Delegate vector Resources to a supplied pyogrio module."""

    name = "pyogrio"
    priority = 10
    _formats = frozenset({"shapefile", "geojson", "gpkg", "flatgeobuf"})

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        return (
            resource.format or ""
        ).lower() in self._formats and self.name in dependencies

    def open(self, resource: Resource, runtime: Any) -> Any:
        attributes = _attributes(resource)
        options: Dict[str, Any] = {}
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options["encoding"] = encoding
        try:
            return runtime.read_dataframe(resource.uri, **options)
        except Exception as error:
            raise ResourceAccessError(
                f"pyogrio could not open {resource.uri!r}"
            ) from error
