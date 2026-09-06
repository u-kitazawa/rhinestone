"""Public facade for built-in Source definitions."""

from typing import Dict, Tuple

from .catalogs import load_source_definitions
from .models import SourceDefinition

_BUILTINS: Dict[str, SourceDefinition] = {
    source.id: source for source in load_source_definitions()
}


def _builtin(source_id: str) -> SourceDefinition:
    return _BUILTINS[source_id]


GEOSPATIAL_JP = _builtin("geospatial-jp")
ESTAT = _builtin("estat")
PLATEAU = _builtin("plateau")
GSI = _builtin("gsi")
ODPT = _builtin("odpt")

ALL: Tuple[SourceDefinition, ...] = tuple(_BUILTINS.values())

__all__ = [
    "ALL",
    "ESTAT",
    "GEOSPATIAL_JP",
    "GSI",
    "ODPT",
    "PLATEAU",
]
