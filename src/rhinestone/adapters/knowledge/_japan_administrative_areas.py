"""Bundled Japanese administrative-area snapshot loaded from JSON."""

import json
from importlib.resources import files
from typing import cast

from .models import AdministrativeArea
from .space import BoundingBox

_rows = cast(
    list[dict[str, object]],
    json.loads(
        files("rhinestone.adapters.knowledge")
        .joinpath("japan_administrative_areas.json")
        .read_text(encoding="utf-8")
    ),
)

JAPAN_ADMINISTRATIVE_AREAS = tuple(
    AdministrativeArea(
        canonical_name=cast(str, row["canonical_name"]),
        code=cast(str, row["code"]),
        aliases=tuple(cast(list[str], row["aliases"])),
        bbox=BoundingBox(*cast(tuple[float, float, float, float], tuple(cast(list[float], row["bbox"])))),
        snapshot_date=cast(str, row["snapshot_date"]),
        source_url=cast(str, row["source_url"]),
    )
    for row in _rows
)

__all__ = ["JAPAN_ADMINISTRATIVE_AREAS"]
