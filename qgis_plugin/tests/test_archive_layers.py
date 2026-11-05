"""Logical archive layers must not become thousands of independent tiles."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "archive_layers", Path(__file__).parents[1] / "rhinestone_search/archive_layers.py"
)
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def scene(uri):
    return {"asset": {"version": "1.0"}, "root": {"content": {"uri": uri}}}


def test_scene_and_mvt_are_discovered_as_two_logical_layers(tmp_path):
    write(tmp_path, "buildings/tileset.json", scene("data/tile.b3dm"))
    (tmp_path / "buildings/data").mkdir()
    (tmp_path / "buildings/data/tile.b3dm").touch()
    write(
        tmp_path,
        "roads/metadata.json",
        {"format": "pbf", "minzoom": 8, "maxzoom": 16, "bounds": "139,35,140,36"},
    )
    tile = tmp_path / "roads/8/227/100.mvt"
    tile.parent.mkdir(parents=True)
    tile.touch()
    result = archive.discover_tiles(tmp_path)
    assert [c["kind"] for c in result["tile_layers"]] == ["scene", "vector-tile"]
    assert (
        result["tile_layers"][1]["url"]
        == (tmp_path / "roads").as_uri() + "/{z}/{x}/{y}.mvt"
    )
    assert result["tile_layers"][1]["bounds"] == [139, 35, 140, 36]


def test_nested_tileset_is_not_a_second_layer(tmp_path):
    write(tmp_path, "root/tileset.json", scene("child/nested.json"))
    write(tmp_path, "root/child/nested.json", scene("data.b3dm"))
    (tmp_path / "root/child/data.b3dm").touch()
    assert len(archive.discover_tiles(tmp_path)["tile_layers"]) == 1


@pytest.mark.parametrize(
    "uri",
    [
        "../outside.b3dm",
        "https://example.org/data.b3dm",
        "missing.b3dm",
        "file:///etc/passwd",
    ],
)
def test_external_or_missing_scene_references_are_disabled(tmp_path, uri):
    write(tmp_path, "tileset.json", scene(uri))
    result = archive.discover_tiles(tmp_path)
    assert result["tile_layers"][0]["reason"]


def test_invalid_json_and_ordinary_json_are_not_tile_layers(tmp_path):
    (tmp_path / "broken.json").write_text("invalid")
    write(tmp_path, "geo.json", {"type": "FeatureCollection", "features": []})
    write(tmp_path, "array.json", [])
    assert archive.discover_tiles(tmp_path) == {"tile_layers": [], "tile_roots": []}


def test_tms_pyramid_is_not_silently_treated_as_xyz(tmp_path):
    write(
        tmp_path,
        "metadata.json",
        {"format": "pbf", "scheme": "tms", "minzoom": 0, "maxzoom": 0},
    )
    tile = tmp_path / "0/0/0.pbf"
    tile.parent.mkdir(parents=True)
    tile.touch()
    assert archive.discover_tiles(tmp_path)["tile_layers"][0]["reason"]
