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

    assert len(rows) == 47
    assert {row["code"] for row in rows} == {
        f"{number:02d}" for number in range(1, 48)
    }
    assert {row["snapshot_date"] for row in rows} == {"2025-01-01"}
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


def test_simplified_snapshot_keeps_island_limit_explicit() -> None:
    adapter = StaticAdministrativeAreaAdapter(JAPAN_ADMINISTRATIVE_AREAS)
    tokyo = adapter.resolve_area("13")
    kanagawa = adapter.resolve_area("神奈川")

    assert tokyo.canonical_name == "東京都"
    assert tokyo.bbox.as_tuple() == (
        138.9429, 24.224799, 153.986554, 35.897436
    )
    assert kanagawa.code == "14"
    assert kanagawa.snapshot_date == "2025-01-01"
