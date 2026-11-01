"""Public search values for canonical data representations."""

from enum import Enum

from .definitions import FORMAT_CATEGORIES


class Format(str, Enum):
    """Canonical formats accepted by search conditions."""

    UNKNOWN = "unknown"
    CITYGML = "citygml"
    COG = "cog"
    CSV = "csv"
    FLATGEOBUF = "flatgeobuf"
    GEOJSON = "geojson"
    GEOTIFF = "geotiff"
    GML = "gml"
    KML = "kml"
    GPKG = "gpkg"
    JSON = "json"
    NETCDF = "netcdf"
    SHAPEFILE = "shapefile"
    ZIP = "zip"
    WMS = "wms"
    WFS = "wfs"
    API = "api"
    OGC_API_FEATURES = "ogc-api-features"


class FormatPreset(str, Enum):
    """Named format sets intended for a downstream runtime."""

    PYOGRIO = "pyogrio"


FORMAT_PRESETS = {
    FormatPreset.PYOGRIO: frozenset(
        Format(name)
        for name, category in FORMAT_CATEGORIES.items()
        if category == "vector"
    )
}


def expand_formats(values: tuple[Format | FormatPreset, ...]) -> frozenset[Format]:
    """Expand concrete values and presets into one OR-matched format set."""
    expanded: set[Format] = set()
    for value in values:
        if isinstance(value, FormatPreset):
            expanded.update(FORMAT_PRESETS[value])
        else:
            expanded.add(value)
    return frozenset(expanded)


__all__ = ["FORMAT_PRESETS", "Format", "FormatPreset", "expand_formats"]
