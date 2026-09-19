"""Structural checks for committed Showcase notebooks.

Live Provider access and optional GIS runtimes remain outside the normal CI gate.
"""

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "showcase"
NOTEBOOK = SHOWCASE / "01_ckan_search_to_map.ipynb"


def _notebook() -> dict[str, Any]:
    value: Any = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _cells(notebook: dict[str, Any]) -> list[dict[str, Any]]:
    value = notebook["cells"]
    assert isinstance(value, list)
    cells: list[dict[str, Any]] = []
    for raw_cell in cast(list[Any], value):
        assert isinstance(raw_cell, dict)
        cells.append(cast(dict[str, Any], raw_cell))
    return cells


def _sources(notebook: dict[str, Any]) -> str:
    source: list[str] = []
    for cell in _cells(notebook):
        value = cell.get("source", [])
        assert isinstance(value, list)
        lines = cast(list[Any], value)
        assert all(isinstance(line, str) for line in lines)
        source.extend(cast(list[str], lines))
    return "".join(source)


def test_showcase_readme_links_to_notebook_and_colab() -> None:
    readme = (SHOWCASE / "README.md").read_text(encoding="utf-8")

    assert "01_ckan_search_to_map.ipynb" in readme
    assert "colab.research.google.com" in readme
    assert "live Provider" in readme


def test_ckan_showcase_notebook_has_the_complete_explicit_flow() -> None:
    notebook = _notebook()

    assert notebook["nbformat"] == 4
    metadata = notebook["metadata"]
    assert isinstance(metadata, dict)
    assert "kernelspec" in metadata
    assert any(
        isinstance(cell, dict) and cell.get("cell_type") == "markdown"
        for cell in _cells(notebook)
    )
    source = _sources(notebook)
    for marker in (
        "sources.GEOSPATIAL_JP",
        'app.search(text="河川"',
        "widgets.Dropdown",
        "app.resolve(selected)",
        'resource.open("pyogrio")',
        "import folium",
        "folium.GeoJson",
        "map_view.fit_bounds",
        "GSI_STANDARD_TILES",
    ):
        assert marker in source


def test_showcase_notebook_commits_safe_executed_output() -> None:
    serialized = NOTEBOOK.read_text(encoding="utf-8")
    notebook = _notebook()

    assert "rhinestone-showcase-" not in serialized
    assert "access_token" not in serialized.casefold()
    assert "authorization" not in serialized.casefold()
    assert "Access blocked" not in serialized
    for cell in _cells(notebook):
        if cell.get("cell_type") != "code":
            continue
        outputs = cell.get("outputs", [])
        assert isinstance(outputs, list)
        for raw_output in cast(list[Any], outputs):
            assert isinstance(raw_output, dict)
            output = cast(dict[str, Any], raw_output)
            data = output.get("data", {})
            assert isinstance(data, dict)
            if output.get("output_type") == "execute_result" and "text/html" in data:
                return
    raise AssertionError("Showcase notebook must commit its interactive map output")


def test_showcase_notebook_code_cells_compile() -> None:
    notebook = _notebook()

    for index, cell in enumerate(_cells(notebook)):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cast(list[str], cell["source"]))
        compile(source, f"{NOTEBOOK} cell {index}", "exec")
