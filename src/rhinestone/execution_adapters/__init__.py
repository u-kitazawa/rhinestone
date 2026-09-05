"""Built-in adapters that delegate selected Resources to user-owned runtimes."""

from typing import Any, Dict, FrozenSet, List, Mapping, cast
from xml.etree.ElementTree import Element, SubElement, tostring

from ..errors import ResourceAccessError
from ..models import FileAccessPlan, Resource
from .json_service import JsonServiceAdapter

__all__ = [
    "GdalAdapter",
    "JsonServiceAdapter",
    "PyogrioAdapter",
    "RasterioAdapter",
    "resource_attributes",
]


def resource_attributes(resource: Resource) -> Mapping[str, Any]:
    for candidate in resource.source.candidates:
        if candidate.uri == resource.uri and candidate.attributes.get(
            "matches_config", True
        ):
            return candidate.attributes
    return {}


class GdalAdapter:
    """Translate Resources into calls understood by a supplied GDAL module."""

    name = "gdal"
    priority = 20
    _formats = frozenset(
        {"shapefile", "geotiff", "cog", "netcdf", "wms", "gml", "citygml"}
    )

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
        tile = resource.access_plan.options.get("tile")
        return self.name in dependencies and (
            (resource.format or "").lower() in self._formats
            or (
                isinstance(tile, Mapping)
                and cast(Mapping[str, Any], tile).get("scheme") == "xyz"
            )
        )

    def open(self, resource: Resource, runtime: Any) -> Any:
        attributes = resource_attributes(resource)
        uri = resource.uri
        tile = resource.access_plan.options.get("tile")
        if tile is not None:
            uri = self.tile_xml(tile)
        archive = attributes.get("archive")
        if isinstance(resource.access_plan, FileAccessPlan):
            archive = resource.access_plan.archive or archive
        if archive == "zip":
            uri = (
                "/vsizip//vsicurl/" + uri
                if uri.startswith(("http://", "https://"))
                else "/vsizip/" + uri
            )
            member = resource.access_plan.options.get("entry_point")
            if member:
                uri += "/" + member
        options: List[str] = []
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options.append("ENCODING=" + encoding.upper())
        try:
            result = runtime.OpenEx(uri, open_options=tuple(options))
            if result is None:
                raise ResourceAccessError("GDAL returned no dataset")
            return result
        except Exception as error:
            raise ResourceAccessError(
                f"GDAL could not open {resource.uri!r}"
            ) from error

    @staticmethod
    def tile_xml(tile: Mapping[str, Any]) -> str:
        root = Element("GDAL_WMS")
        service = SubElement(root, "Service", name="TMS")
        template = tile["url"]
        for name in ("x", "y", "z"):
            template = template.replace("{" + name + "}", "${" + name + "}")
        SubElement(service, "ServerUrl").text = template
        window = SubElement(root, "DataWindow")
        for key, value in {
            "UpperLeftX": "-20037508.342789244",
            "UpperLeftY": "20037508.342789244",
            "LowerRightX": "20037508.342789244",
            "LowerRightY": "-20037508.342789244",
            "TileLevel": str(tile["max_zoom"]),
            "TileCountX": "1",
            "TileCountY": "1",
            "YOrigin": "top",
        }.items():
            SubElement(window, key).text = value
        for key, value in {
            "Projection": "EPSG:3857",
            "BlockSizeX": "256",
            "BlockSizeY": "256",
            "BandsCount": "3",
            "OverviewCount": str(tile["max_zoom"] - tile["min_zoom"]),
        }.items():
            SubElement(root, key).text = value
        return tostring(root, encoding="unicode")


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
        attributes = resource_attributes(resource)
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
