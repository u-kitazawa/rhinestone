"""Bundled administrative areas must remain reviewable as JSON."""

import json
from importlib.resources import files
from typing import Any, cast

from rhinestone.adapters.knowledge import StaticAdministrativeAreaAdapter
from rhinestone.adapters.knowledge._japan_administrative_areas import (
    JAPAN_ADMINISTRATIVE_AREAS,
)


def test_bundled_areas_match_json_snapshot() -> None:
    data = json.loads(
        files("rhinestone.adapters.knowledge")
        .joinpath("japan_administrative_areas.json")
        .read_text(encoding="utf-8")
    )
    rows = cast(list[dict[str, Any]], data)

    assert rows
    assert [area.code for area in JAPAN_ADMINISTRATIVE_AREAS] == [
        row["code"] for row in rows
    ]
    adapter = StaticAdministrativeAreaAdapter(JAPAN_ADMINISTRATIVE_AREAS)
    for row in rows:
        area = adapter.resolve_area(row["code"])
        assert area.canonical_name == row["canonical_name"]
        assert list(area.aliases) == row["aliases"]
        assert list(area.bbox.as_tuple()) == row["bbox"]
        assert area.snapshot_date == row["snapshot_date"]
        assert area.source_url == row["source_url"]
