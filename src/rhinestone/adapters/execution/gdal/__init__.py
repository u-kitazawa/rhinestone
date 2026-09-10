"""Built-in adapters that delegate selected Resources to user-owned runtimes."""

from typing import Any, FrozenSet, List, Mapping, cast
from xml.etree.ElementTree import Element, SubElement, tostring

from ....errors import DestinationNotAllowedError, ResourceAccessError
from ....models import FileAccessPlan, Resource
from ....security import DestinationPolicy, DestinationRule
from .._locator import authorize_runtime_locator
from .._resource import resource_attributes
from ..base import ExecutionAdapter


class GdalAdapter(ExecutionAdapter):
    """Translate Resources into calls understood by a supplied GDAL module."""

    name = "gdal"
    priority = 20
    _formats = frozenset(
        {"shapefile", "geotiff", "cog", "netcdf", "wms", "gml", "citygml"}
    )
    _strict_drivers = {"cog": ("GTiff",), "geotiff": ("GTiff",)}

    def __init__(self, destination_policy: DestinationPolicy | None = None) -> None:
        super().__init__(destination_policy)

    def supports(self, resource: Resource, dependencies: FrozenSet[str]) -> bool:
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
        policy = destination_policy or self._destination_policy
        uri = self._runtime_uri(resource, policy)
        authorize_runtime_locator(uri, policy)
        allowed_drivers = self._allowed_drivers(resource, policy)
        attributes = resource_attributes(resource)
        options: List[str] = []
        encoding = attributes.get("encoding")
        if isinstance(encoding, str):
            options.append("ENCODING=" + encoding.upper())
        try:
            runtime_options: dict[str, Any] = {"open_options": tuple(options)}
            if allowed_drivers is not None:
                runtime_options["allowed_drivers"] = allowed_drivers
            result = runtime.OpenEx(uri, **runtime_options)
            if result is None:
                raise ResourceAccessError("GDAL returned no dataset")
            return result
        except Exception as error:
            raise ResourceAccessError(
                f"GDAL could not open {resource.uri!r}"
            ) from error

    def authorize(
        self,
        resource: Resource,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> None:
        policy = destination_policy or self._destination_policy
        authorize_runtime_locator(self._runtime_uri(resource, policy), policy)
        self._allowed_drivers(resource, policy)

    @classmethod
    def _allowed_drivers(
        cls, resource: Resource, policy: DestinationPolicy
    ) -> tuple[str, ...] | None:
        if policy.level != "strict":
            return None
        drivers = cls._strict_drivers.get((resource.format or "").lower())
        if drivers is None or resource.access_plan.options.get("tile") is not None:
            raise DestinationNotAllowedError(
                "GDAL strict policy does not allow this dataset driver"
            )
        return drivers

    @staticmethod
    def _runtime_uri(resource: Resource, policy: DestinationPolicy) -> str:
        attributes = resource_attributes(resource)
        uri = resource.uri
        tile = resource.access_plan.options.get("tile")
        if tile is not None:
            if not isinstance(tile, Mapping):
                raise ResourceAccessError("GDAL tile options must be an object")
            tile = cast(Mapping[str, Any], tile)
            tile_url = tile.get("url")
            if not isinstance(tile_url, str):
                raise ResourceAccessError("GDAL tile URL must be a string")
            if policy.level == "strict" and DestinationRule.from_url(tile_url) is None:
                raise DestinationNotAllowedError(
                    "GDAL tile URL must be an authorized HTTP(S) destination"
                )
            policy.authorize(tile_url)
            uri = GdalAdapter.tile_xml(tile)
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
        return uri

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
