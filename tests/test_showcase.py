"""Structural checks for committed Showcase notebooks.

Live Provider access and optional GIS runtimes remain outside the normal CI gate.
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "showcase"
OFFLINE_NOTEBOOK = SHOWCASE / "01_search_and_resource.ipynb"
MAP_NOTEBOOK = SHOWCASE / "02_ckan_search_to_map.ipynb"


def load_notebook(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
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


def test_offline_showcase_has_portable_metadata_and_executed_cells() -> None:
    notebook = load_notebook(OFFLINE_NOTEBOOK)

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"
    assert notebook["metadata"]["colab"]["name"] == OFFLINE_NOTEBOOK.name

    code_cells = [
        cell for cell in notebook_cells(notebook) if cell["cell_type"] == "code"
    ]
    assert code_cells
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert all("ci" in cell["metadata"].get("tags", []) for cell in code_cells)

    setup_source = "".join(code_cells[0]["source"])
    assert "@fb673a0a0644333e2e4c0aad002973f817876d29" in setup_source
    assert "@develop" not in setup_source


def test_offline_showcase_code_compiles_and_runs_offline(
    capsys: pytest.CaptureFixture[str],
) -> None:
    notebook = load_notebook(OFFLINE_NOTEBOOK)
    namespace: dict[str, object] = {}

    for index, cell in enumerate(notebook_cells(notebook)):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        exec(
            compile(source, f"{OFFLINE_NOTEBOOK.name}:cell-{index}", "exec"), namespace
        )

    output = capsys.readouterr().out
    assert "Providers: ('gsi',)\n" in output
    assert "Results: 1\n" in output
    assert "Title: 標準地図\n" in output
    assert "Provider / dataset: gsi / std\n" in output
    assert "AccessPlan: RemoteDatasetPlan (remote-dataset)\n" in output


def test_offline_showcase_outputs_are_small_and_contain_no_credentials() -> None:
    notebook = load_notebook(OFFLINE_NOTEBOOK)
    outputs = [
        output
        for cell in notebook_cells(notebook)
        for output in cell.get("outputs", [])
    ]
    serialized_outputs = json.dumps(outputs, ensure_ascii=False, sort_keys=True)

    assert len(serialized_outputs.encode()) < 50_000
    lowered = serialized_outputs.lower()
    for marker in ("api_key", "api-token", "bearer ", "consumer_key", "secret"):
        assert marker not in lowered


def test_ckan_showcase_has_the_complete_explicit_flow() -> None:
    notebook = load_notebook(MAP_NOTEBOOK)

    assert notebook["nbformat"] == 4
    assert "kernelspec" in notebook["metadata"]
    assert any(cell.get("cell_type") == "markdown" for cell in notebook_cells(notebook))
    source = notebook_source(notebook)
    for marker in (
        "sources.GEOSPATIAL_JP",
        'app.search(text="河川"',
        'dependencies={"pyogrio": pyogrio}',
        "PYOGRIO_VECTOR_FORMATS",
        "item.format in PYOGRIO_VECTOR_FORMATS",
        "item.access_plan.archive is None",
        'resource.open("pyogrio")',
        "import folium",
        "folium.GeoJson",
        "map_view.fit_bounds",
        "GSI_STANDARD_TILES",
    ):
        assert marker in source


def test_ckan_showcase_keeps_no_stale_execution_output() -> None:
    serialized = MAP_NOTEBOOK.read_text(encoding="utf-8")
    notebook = load_notebook(MAP_NOTEBOOK)

    assert "rhinestone-showcase-" not in serialized
    assert "access_token" not in serialized.casefold()
    assert "authorization" not in serialized.casefold()
    assert "Access blocked" not in serialized
    assert all(
        cell.get("outputs", []) == []
        for cell in notebook_cells(notebook)
        if cell.get("cell_type") == "code"
    )


def test_showcase_notebook_code_cells_compile() -> None:
    for notebook_path in (OFFLINE_NOTEBOOK, MAP_NOTEBOOK):
        for index, cell in enumerate(notebook_cells(load_notebook(notebook_path))):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell["source"])
            compile(source, f"{notebook_path} cell {index}", "exec")


def test_showcase_readme_lists_both_notebooks_and_live_boundaries() -> None:
    readme = (SHOWCASE / "README.md").read_text(encoding="utf-8")

    assert OFFLINE_NOTEBOOK.name in readme
    assert MAP_NOTEBOOK.name in readme
    assert "colab.research.google.com" in readme
    assert (
        "codex/showcase-interactive-map/showcase/02_ckan_search_to_map.ipynb" in readme
    )
    assert "live Provider" in readme
    assert "ライブ Provider への疎通は通常 CI の必須条件にしません" in readme
