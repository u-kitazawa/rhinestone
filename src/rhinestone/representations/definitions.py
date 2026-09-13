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
        "shp": "shapefile",
        "tiff": "geotiff",
    }
)

MEDIA_TYPE_FORMATS: Mapping[str, str] = MappingProxyType(
    {
        "application/geo+json": "geojson",
        "application/geopackage+sqlite3": "gpkg",
        "application/gml+xml": "gml",
        "application/json": "json",
        "application/vnd.google-earth.kml+xml": "kml",
        "image/tiff": "geotiff",
        "text/csv": "csv",
    }
)

CONTAINER_MEDIA_TYPES: Mapping[str, str] = MappingProxyType({"application/zip": "zip"})

FORMAT_CATEGORIES: Mapping[str, str] = MappingProxyType(
    {
        "citygml": "vector",
        "cog": "raster",
        "csv": "table",
        "flatgeobuf": "vector",
        "geojson": "vector",
        "geotiff": "raster",
        "gml": "vector",
        "kml": "vector",
        "gpkg": "vector",
        "json": "table",
        "netcdf": "raster",
        "shapefile": "vector",
        "zip": "archive",
        "wms": "service",
        "wfs": "service",
        "api": "service",
        "ogc-api-features": "service",
    }
)

CANONICAL_FORMATS = frozenset(FORMAT_CATEGORIES)

__all__ = [
    "CANONICAL_FORMATS",
    "CONTAINER_MEDIA_TYPES",
    "FORMAT_ALIASES",
    "FORMAT_CATEGORIES",
    "MEDIA_TYPE_FORMATS",
]
