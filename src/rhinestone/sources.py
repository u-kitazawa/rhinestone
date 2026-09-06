"""Built-in external source definitions."""

from typing import Tuple

from .models import SourceDefinition

GEOSPATIAL_JP = SourceDefinition(
    id="geospatial-jp",
    adapter_type="ckan",
    settings={"endpoint": "https://www.geospatial.jp/ckan"},
)

ESTAT = SourceDefinition(
    id="estat",
    adapter_type="estat",
)

PLATEAU = SourceDefinition(
    id="plateau",
    adapter_type="plateau",
    settings={"endpoint": "https://www.geospatial.jp/ckan"},
)

GSI = SourceDefinition(
    id="gsi",
    adapter_type="gsi-tile",
)

ODPT = SourceDefinition(
    id="odpt",
    adapter_type="odpt",
)

ALL: Tuple[SourceDefinition, ...] = (
    GEOSPATIAL_JP,
    ESTAT,
    PLATEAU,
    GSI,
    ODPT,
)

__all__ = [
    "ALL",
    "ESTAT",
    "GEOSPATIAL_JP",
    "GSI",
    "ODPT",
    "PLATEAU",
]
