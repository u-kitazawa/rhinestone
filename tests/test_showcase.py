import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "showcase"
NOTEBOOK = SHOWCASE / "01_search_and_resource.ipynb"


def load_notebook() -> dict[str, Any]:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def test_showcase_notebook_has_portable_metadata_and_executed_cells() -> None:
    notebook = load_notebook()

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == "python3"
    assert notebook["metadata"]["colab"]["name"] == NOTEBOOK.name

    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    assert all(cell["execution_count"] is not None for cell in code_cells)
    assert all("ci" in cell["metadata"].get("tags", []) for cell in code_cells)


def test_showcase_notebook_code_compiles_and_runs_offline(
    capsys: pytest.CaptureFixture[str],
) -> None:
    notebook = load_notebook()
    namespace: dict[str, object] = {}

    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        exec(compile(source, f"{NOTEBOOK.name}:cell-{index}", "exec"), namespace)

    output = capsys.readouterr().out
    assert "Providers: ('gsi',)\n" in output
    assert "Results: 1\n" in output
    assert "Title: 標準地図\n" in output
    assert "Provider / dataset: gsi / std\n" in output
    assert "AccessPlan: RemoteDatasetPlan (remote-dataset)\n" in output


def test_showcase_notebook_outputs_are_small_and_contain_no_credentials() -> None:
    notebook = load_notebook()
    output_text = ""
    for cell in notebook["cells"]:
        for output in cell.get("outputs", []):
            output_text += "".join(output.get("text", []))

    assert len(output_text.encode()) < 50_000
    lowered = output_text.lower()
    for marker in ("api_key", "api-token", "bearer ", "consumer_key", "secret"):
        assert marker not in lowered


def test_showcase_readme_links_the_notebook_and_states_live_boundaries() -> None:
    readme = (SHOWCASE / "README.md").read_text(encoding="utf-8")

    assert "01_search_and_resource.ipynb" in readme
    assert "ライブProviderへの疎通は通常CIの必須条件にしません" in readme
    assert "今後追加します" in readme
