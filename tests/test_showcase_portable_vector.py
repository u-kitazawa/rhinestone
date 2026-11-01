"""Exercise the actual producer/receiver cells without live services or GIS deps."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import rhinestone
from rhinestone import AccessPlan, Catalog, Provider, Resource, SearchResults, configure
from rhinestone.errors import ResourceAccessError
from rhinestone.models import SearchDiagnostic

ROOT = Path(__file__).parents[1] / "showcase"
PRODUCER = "02_open_vector.ipynb"
RECEIVER = "03_portable_vector.ipynb"
URI = (
    "https://nasu-ckan.s3.amazonaws.com/ckan/resources/"
    "d94a1299-e0fb-4c9a-9a9f-aac7dcb97763/011201.json"
)


def cells(name: str) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in json.loads((ROOT / name).read_text())["cells"]}


def run(name: str, cell_id: str, namespace: dict[str, Any]) -> None:
    source = "".join(cells(name)[cell_id]["source"])
    exec(compile(source, f"{name}:{cell_id}", "exec"), namespace)


def resource() -> Resource:
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "fixture",
                    "static",
                    {
                        "items": {
                            "selected": {
                                "metadata": {"title": "Parks"},
                                "candidates": [{"uri": URI, "format": "geojson"}],
                            }
                        }
                    },
                ),
            )
        )
    )
    return app.search(text="Parks")[0]


@pytest.mark.parametrize("name", [PRODUCER, RECEIVER])
def test_notebook_contract_and_compilation(name: str) -> None:
    notebook = cells(name)
    source = "".join("".join(c["source"]) for c in notebook.values())
    for marker in ("CC BY 2.1 JP", "2016-04-04", "名称", "写真"):
        assert marker in source
    assert "@9bae025b08357d23e5f5339c25a777a1445da176" in source
    for c in notebook.values():
        if c["cell_type"] == "code":
            compile("".join(c["source"]), name, "exec")
            assert not any(o.get("output_type") == "error" for o in c["outputs"])
    assert len(json.dumps(notebook).encode()) < 200_000


@pytest.mark.parametrize("has_diagnostic", [False, True])
def test_discover_empty_stops_before_selection(
    monkeypatch: pytest.MonkeyPatch, has_diagnostic: bool
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
        if has_diagnostic
        else ()
    )
    results = SearchResults.from_grouped({}, diagnostics=diagnostics)

    def search(**kwargs: Any) -> SearchResults:
        return results

    monkeypatch.setattr(rhinestone, "search", search)
    namespace: dict[str, Any] = {}
    run(PRODUCER, "inputs", namespace)
    with pytest.raises(ValueError, match="Provider" if has_diagnostic else "検索0件"):
        run(PRODUCER, "discover", namespace)


def test_discover_partial_success_preserves_diagnostics_and_selection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    selected = resource()
    results = SearchResults.from_grouped(
        {"fixture": (selected,)},
        diagnostics=(
            SearchDiagnostic(
                "other", frozenset(), reason="provider_failure", failure_type="response"
            ),
        ),
    )

    def search(**kwargs: Any) -> SearchResults:
        return results

    monkeypatch.setattr(rhinestone, "search", search)
    namespace: dict[str, Any] = {}
    run(PRODUCER, "inputs", namespace)
    run(PRODUCER, "discover", namespace)
    run(PRODUCER, "select", namespace)
    assert namespace["resource"] is selected
    assert "Diagnostic: other provider_failure response" in capsys.readouterr().out


@pytest.mark.parametrize("count", [0, 2])
def test_selection_never_uses_implicit_first_or_stale_resource(count: int) -> None:
    namespace = {
        "results": [resource()] * count,
        "SELECTED_URI": URI,
        "resource": object(),
    }
    with pytest.raises(ValueError, match="一意"):
        run(PRODUCER, "select", namespace)
    assert namespace["resource"] is None


def test_export_and_independent_receiver_without_search(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    selected = resource()
    run(PRODUCER, "export", {"resource": selected})
    path = tmp_path / "vector-plan.json"
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        run(PRODUCER, "export", {"resource": selected})
    assert path.read_bytes() == original

    def no_search(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("receiver must not search")

    monkeypatch.setattr(rhinestone, "search", no_search)
    namespace: dict[str, Any] = {}
    run(RECEIVER, "receive", namespace)
    assert namespace["received_plan"] == selected.access_plan
    calls: list[str] = []

    class Frame:
        crs = "EPSG:4979"

        def __len__(self) -> int:
            return 2

    def read_dataframe(uri: str) -> Frame:
        calls.append(uri)
        return Frame()

    monkeypatch.setitem(
        sys.modules, "pyogrio", SimpleNamespace(read_dataframe=read_dataframe)
    )
    run(RECEIVER, "open", namespace)
    assert calls == [URI]


@pytest.mark.parametrize(
    "case", ["missing", "oversize", "json", "destination", "format"]
)
def test_receiver_rejects_unusable_input(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str
) -> None:
    monkeypatch.chdir(tmp_path)
    payload = configure().plan(resource()).to_dict()
    if case == "destination":
        payload["uri"] = "https://untrusted.example/other.geojson"
    if case == "format":
        payload["format"] = "gml"
    if case != "missing":
        content = "x" * 65537 if case == "oversize" else json.dumps(payload)
        (tmp_path / "vector-plan.json").write_text("{" if case == "json" else content)
    with pytest.raises(ValueError):
        run(RECEIVER, "receive", {})


@pytest.mark.parametrize("name", [PRODUCER, RECEIVER])
def test_native_open_failure_retains_cause_and_clears_frame(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    cause = OSError("native access failed")

    def read_dataframe(*args: Any, **kwargs: Any) -> Any:
        raise cause

    monkeypatch.setitem(
        sys.modules, "pyogrio", SimpleNamespace(read_dataframe=read_dataframe)
    )
    selected = resource()
    namespace = {
        "resource": selected,
        "frame": object(),
        "received_plan": AccessPlan.from_dict(configure().plan(selected).to_dict()),
        "receiving_app": configure(
            catalog=Catalog(
                (Provider("allowed", "direct", {"uri": URI, "format": "geojson"}),)
            )
        ),
    }
    with pytest.raises(ResourceAccessError) as error:
        run(name, "open", namespace)
    assert error.value.__cause__ is cause
    assert namespace["frame"] is None
