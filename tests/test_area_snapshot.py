"""Bundled administrative areas must remain reviewable as JSON."""

import json
from importlib.resources import files
from typing import Any, cast

import pytest

from rhinestone.adapters.knowledge import StaticAdministrativeAreaAdapter
from rhinestone.errors import KnowledgeResolutionError
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

    assert len(rows) == 1965
    assert {row["code"] for row in rows if len(row["code"]) == 2} == {
        f"{number:02d}" for number in range(1, 48)
    }
    assert len({row["code"] for row in rows if len(row["code"]) == 5}) == 1918
    assert len({row["canonical_name"] for row in rows}) == len(rows)
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


def test_bundled_prefectures_and_municipalities_resolve() -> None:
    adapter = StaticAdministrativeAreaAdapter(JAPAN_ADMINISTRATIVE_AREAS)
    tokyo = adapter.resolve_area("13")
    kanagawa = adapter.resolve_area("神奈川")
    yokohama = adapter.resolve_area("14100")
    ward = adapter.resolve_area("14101")
    island = adapter.resolve_area("01696")

    assert tokyo.canonical_name == "東京都"
    assert tokyo.bbox.as_tuple() == (
        136.06979, 20.42276, 153.9866, 35.89842
    )
    assert kanagawa.code == "14"
    assert kanagawa.snapshot_date == "2025-01-01"
    assert yokohama.canonical_name == "神奈川県横浜市"
    assert adapter.resolve_area("横浜市") is yokohama
    assert ward.canonical_name == "神奈川県横浜市鶴見区"
    assert yokohama.bbox.west <= ward.bbox.west <= ward.bbox.east
    assert ward.bbox.east <= yokohama.bbox.east
    assert island.canonical_name == "北海道国後郡泊村"
    with pytest.raises(KnowledgeResolutionError, match="ambiguous"):
        adapter.resolve_area("泊村")
