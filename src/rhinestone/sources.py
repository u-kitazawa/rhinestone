"""Built-in external source definitions."""

import json
from importlib import resources
from typing import Any, Dict, Tuple, cast

from .models import SourceDefinition


def _load_catalog(name: str) -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(resources.read_text("rhinestone.catalogs", name)),
    )


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
    adapter_type="static",
    settings={"items": _load_catalog("gsi_tiles.json")},
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
