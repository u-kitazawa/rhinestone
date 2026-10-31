"""Validate the redesigned discovery flow and the advanced STAC boundary."""

import json
from pathlib import Path
from typing import Any

import pytest

import rhinestone
from rhinestone import SearchResults
from rhinestone.models import SearchDiagnostic
from tests.test_showcase_portable_vector import resource

SHOWCASE = Path(__file__).parents[1] / "showcase"


def notebook(path: str) -> dict[str, Any]:
    return json.loads((SHOWCASE / path).read_text(encoding="utf-8"))


def execute(cell_id: str, namespace: dict[str, Any]) -> None:
    cell = next(c for c in notebook("01_discover.ipynb")["cells"] if c["id"] == cell_id)
    exec(compile("".join(cell["source"]), cell_id, "exec"), namespace)


def test_discover_passes_user_conditions_and_lists_grouped_resources(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    selected = resource()
    results = SearchResults.from_grouped({"fixture": (selected,), "empty": ()})
    calls: list[dict[str, Any]] = []

    def search(**kwargs: Any) -> SearchResults:
        calls.append(kwargs)
        return results

    monkeypatch.setattr(rhinestone, "search", search)
    namespace: dict[str, Any] = {}
    execute("inputs", namespace)
    namespace.update(KEYWORD="学校", AREA="東京都")
    execute("discover", namespace)
    assert calls[0]["text"] == "学校"
    assert calls[0]["area"] == "東京都"
    assert calls[0]["limit"] == 3
    output = capsys.readouterr().out
    assert "Provider: fixture Results: 1" in output
    assert "Provider: empty Results: 0" in output
    assert "Parks | geojson" in output
    assert selected.uri in output


@pytest.mark.parametrize("failure", [False, True])
def test_discover_distinguishes_empty_from_provider_failure(
    monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    diagnostics = (
        (
            SearchDiagnostic(
                "catalog",
                frozenset(),
                reason="provider_failure",
                failure_type="metadata",
            ),
        )
        if failure
        else ()
    )
    results = SearchResults.from_grouped({}, diagnostics=diagnostics)

    def search(**kwargs: Any) -> SearchResults:
        return results

    monkeypatch.setattr(rhinestone, "search", search)
    namespace: dict[str, Any] = {}
    execute("inputs", namespace)
    with pytest.raises(ValueError, match="Provider" if failure else "検索0件"):
        execute("discover", namespace)


def test_all_showcase_cells_compile_and_use_current_pins() -> None:
    for path in SHOWCASE.rglob("*.ipynb"):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["metadata"]["colab"]["name"] == path.name
        sources: list[str] = []
        for cell in value["cells"]:
            source = "".join(cell["source"])
            sources.append(source)
            if cell["cell_type"] == "code":
                compile(source, str(path), "exec")
                assert not any(o.get("output_type") == "error" for o in cell["outputs"])
        text = "".join(sources)
        expected_pin = (
            "@bf4b7d98a73f6871b1301c184386abf83cff29a9"
            if path.name == "05_open_raster.ipynb"
            else "@9bae025b08357d23e5f5339c25a777a1445da176"
        )
        assert expected_pin in text
        assert "@develop" not in text


def test_main_entry_points_and_advanced_examples_are_separate() -> None:
    readme = (SHOWCASE / "README.md").read_text(encoding="utf-8")
    expected = {
        "01_discover.ipynb",
        "02_open_vector.ipynb",
        "03_portable_vector.ipynb",
        "04_explore.ipynb",
        "05_open_raster.ipynb",
    }
    assert {p.name for p in SHOWCASE.glob("*.ipynb")} == expected
    for name in expected:
        assert name in readme
        assert f"blob/develop/showcase/{name}" in readme
    assert "advanced/stac_explicit.ipynb" in readme
    assert "advanced/discovery_lineage.ipynb" in readme
    assert "ライブ Provider への疎通は通常 CI の必須条件にしません" in readme


def test_advanced_stac_keeps_explicit_selection_and_bounded_preview() -> None:
    value = notebook("advanced/stac_explicit.ipynb")
    source = "".join("".join(c["source"]) for c in value["cells"])
    for marker in (
        '"collection_id": collection_id',
        '"item_id": item_id',
        '"asset_key": asset_key',
        'resource.open("rasterio", runtime=rasterio)',
        "out_shape=(len(display_indexes), preview_height, preview_width)",
        "Resampling.bilinear",
        "rasterio==1.5.2",
    ):
        assert marker in source
    assert all(c.get("outputs", []) == [] for c in value["cells"])
