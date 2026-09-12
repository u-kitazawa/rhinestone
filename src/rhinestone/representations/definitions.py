"""Definitions for Rhinestone's shared representation vocabulary.

This module contains values only. Normalization behavior lives in
``representations.normalization``.
"""

from types import MappingProxyType
from typing import Mapping

FORMAT_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "geopackage": "gpkg",
        "gtiff": "geotiff",
        "tiff": "geotiff",
    }
)

MEDIA_TYPE_FORMATS: Mapping[str, str] = MappingProxyType(
    {
        "application/geo+json": "geojson",
        "application/geopackage+sqlite3": "gpkg",
        "application/json": "json",
        "application/zip": "zip",
        "image/tiff": "geotiff",
        "text/csv": "csv",
    }
)

FORMAT_CATEGORIES: Mapping[str, str] = MappingProxyType(
    {
        "citygml": "vector",
        "cog": "raster",
        "csv": "table",
        "flatgeobuf": "vector",
        "geojson": "vector",
        "geotiff": "raster",
        "gml": "vector",
        "gpkg": "vector",
        "json": "table",
        "netcdf": "raster",
        "shapefile": "vector",
        "zip": "archive",
    }
)

__all__ = ["FORMAT_ALIASES", "FORMAT_CATEGORIES", "MEDIA_TYPE_FORMATS"]
