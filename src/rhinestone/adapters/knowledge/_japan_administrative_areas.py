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


def _area(row: dict[str, object]) -> AdministrativeArea:
    bounds = cast(list[float], row["bbox"])
    return AdministrativeArea(
        canonical_name=cast(str, row["canonical_name"]),
        code=cast(str, row["code"]),
        aliases=tuple(cast(list[str], row["aliases"])),
        bbox=BoundingBox(bounds[0], bounds[1], bounds[2], bounds[3]),
        snapshot_date=cast(str, row["snapshot_date"]),
        source_url=cast(str, row["source_url"]),
    )


JAPAN_ADMINISTRATIVE_AREAS = tuple(_area(row) for row in _rows)

__all__ = ["JAPAN_ADMINISTRATIVE_AREAS"]
