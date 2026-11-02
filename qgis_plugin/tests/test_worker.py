"""Core boundary and download regression tests, without importing QGIS."""

import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rhinestone import AccessPlan, Reference, configure
from rhinestone.models import SearchDiagnostic
from rhinestone.search import SearchResults

SPEC = importlib.util.spec_from_file_location(
    "worker", Path(__file__).parents[1] / "rhinestone_search/worker.py"
)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def resource(uri="https://example.org/data.json", format="geojson"):
    return configure().load(
        Reference("direct", parameters={"uri": uri, "format": format})
    )


def test_search_preserves_selected_identity_and_diagnostics(monkeypatch):
    first, second = resource(), resource("https://example.org/second.json")
    unknown = resource("https://example.org/a.csv", "csv")
    diagnostics = (
        SearchDiagnostic(
            source_id="failed",
            reason="provider_failure",
            failure_type="response",
            skipped_conditions=frozenset(),
        ),
    )

    def search(**kwargs):
        assert kwargs == {
            "providers": [worker.ProviderId.SEARCH_CKAN_JP],
            "text": "公園",
            "limit": 20,
        }
        return SearchResults.from_grouped(
            {"test": (unknown, first, second)}, diagnostics
        )

    monkeypatch.setattr(worker, "search", search)
    result = worker.execute({"action": "search", "text": "公園"})
    assert [r["resource"]["uri"] for r in result["rows"]] == [
        first.uri,
        second.uri,
        unknown.uri,
    ]
    assert result["rows"][2]["reason"]
    assert result["diagnostics"][0]["failure_type"] == "response"
    assert result["rows"][1]["resource"] == second.to_dict()


@pytest.mark.parametrize(
    "plan",
    [
        AccessPlan(
            "file",
            "https://example.org/data.zip",
            "shapefile",
            options={"archive": "zip"},
        ),
        AccessPlan("file", "https://example.org/data.csv", "csv"),
        AccessPlan("file", "/tmp/data.json", "geojson"),
        AccessPlan(
            "file", "https://example.org/data.json", "geojson", credential="secret"
        ),
    ],
)
def test_unsupported_plans_are_not_silently_opened(plan):
    assert worker.unsupported(plan)


class Response(io.BytesIO):
    url = "https://example.org/selected.json"


def test_download_exact_selected_resource_and_retains_plan(monkeypatch, tmp_path):
    selected = resource("https://example.org/selected.json")
    calls = []

    def fetch(uri, timeout):
        calls.append((uri, timeout))
        return Response(b'{"type":"FeatureCollection","features":[]}')

    monkeypatch.setattr(worker, "urlopen", fetch)
    target = tmp_path / "data.geojson"
    result = worker.execute(
        {"action": "download", "resource": selected.to_dict(), "target": str(target)}
    )
    assert calls == [(selected.uri, 30)]
    assert result["resource"] == selected.to_dict()
    assert result["plan"] == configure().plan(selected).to_dict()
    assert json.loads(target.read_text())["features"] == []
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize(
    "body", [b"<html>error</html>", b'{"error":"unavailable"}', b"[]"]
)
def test_invalid_geojson_cleans_partial_file(monkeypatch, tmp_path, body):
    monkeypatch.setattr(worker, "urlopen", lambda *a, **kw: Response(body))
    target = tmp_path / "data.geojson"
    with pytest.raises(ValueError):
        worker.execute(
            {
                "action": "download",
                "resource": resource().to_dict(),
                "target": str(target),
            }
        )
    assert list(tmp_path.iterdir()) == []


def test_size_limit_cleans_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "MAX_BYTES", 3)
    monkeypatch.setattr(worker, "urlopen", lambda *a, **kw: Response(b"1234"))
    with pytest.raises(ValueError, match="50 MiB"):
        worker.execute(
            {
                "action": "download",
                "resource": resource().to_dict(),
                "target": str(tmp_path / "data.geojson"),
            }
        )
    assert list(tmp_path.iterdir()) == []


def test_main_sanitizes_network_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        worker.sys, "stdin", io.StringIO('{"action":"search","text":"公園"}')
    )

    def fail(**kwargs):
        raise OSError("https://secret@example.org/private")

    monkeypatch.setattr(worker, "search", fail)
    worker.main()
    assert json.loads(capsys.readouterr().out) == {"ok": False, "error": "OSError"}


def test_planning_failure_is_disabled(monkeypatch):
    monkeypatch.setattr(
        worker, "search", lambda **kw: SearchResults({"test": (resource(),)})
    )

    def fail(value):
        raise ValueError("bad plan")

    monkeypatch.setattr(worker, "configure", lambda: SimpleNamespace(plan=fail))
    assert (
        "ValueError"
        in worker.execute({"action": "search", "text": "公園"})["rows"][0]["reason"]
    )
