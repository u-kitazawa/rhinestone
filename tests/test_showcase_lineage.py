"""Structural checks for the Discovery lineage Showcase notebook."""

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "showcase"
LINEAGE_NOTEBOOK = SHOWCASE / "04_discovery_lineage.ipynb"


def load_notebook() -> dict[str, Any]:
    value = json.loads(LINEAGE_NOTEBOOK.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def notebook_cells(notebook: dict[str, Any]) -> list[dict[str, Any]]:
    value = notebook["cells"]
    assert isinstance(value, list)
    cells = cast(list[Any], value)
    assert all(isinstance(cell, dict) for cell in cells)
    return [cast(dict[str, Any], cell) for cell in cells]


def notebook_source(notebook: dict[str, Any]) -> str:
    source: list[str] = []
    for cell in notebook_cells(notebook):
        value = cell.get("source", [])
        assert isinstance(value, list)
        lines = cast(list[Any], value)
        assert all(isinstance(line, str) for line in lines)
        source.extend(cast(list[str], lines))
    return "".join(source)


def test_lineage_showcase_keeps_discovery_and_resolution_records_separate() -> None:
    notebook = load_notebook()

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["colab"]["name"] == LINEAGE_NOTEBOOK.name
    source = notebook_source(notebook)
    for marker in (
        "sources.SEARCH_CKAN_JP",
        "item.discovered_by != item.target.source_id",
        "resource = app.resolve(result)",
        "resource.discovery is None",
        "discovery.provenance.provider",
        "resource.provenance.provider",
        "resource.source.raw_metadata",
        "resource.access_plan.kind",
        "flat merge",
    ):
        assert marker in source


def test_lineage_showcase_pins_setup_compiles_and_keeps_no_output() -> None:
    serialized = LINEAGE_NOTEBOOK.read_text(encoding="utf-8")
    notebook = load_notebook()
    source = notebook_source(notebook)

    assert "@697e70d812c06e9a0417d1eb86014c0b18e4a8a5" in source
    assert "@develop" not in source
    assert "access_token" not in serialized.casefold()
    assert "authorization" not in serialized.casefold()
    for index, cell in enumerate(notebook_cells(notebook)):
        if cell.get("cell_type") != "code":
            continue
        code = "".join(cast(list[str], cell["source"]))
        compile(code, f"{LINEAGE_NOTEBOOK.name}:cell-{index}", "exec")
        assert cell.get("outputs", []) == []


def test_showcase_readme_links_to_lineage_notebook_and_colab() -> None:
    readme = (SHOWCASE / "README.md").read_text(encoding="utf-8")

    assert LINEAGE_NOTEBOOK.name in readme
    assert "blob/develop/showcase/04_discovery_lineage.ipynb" in readme
    assert "発見側と解決側" in readme
