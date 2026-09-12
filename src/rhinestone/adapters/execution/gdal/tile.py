"""Translate XYZ tile knowledge into a GDAL WMS definition."""

from typing import Any, Mapping
from xml.etree.ElementTree import Element, SubElement, tostring


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
