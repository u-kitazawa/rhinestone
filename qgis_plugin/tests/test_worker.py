"""Core boundary and download regression tests, without importing QGIS."""

import importlib.util
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from rhinestone import AccessPlan, Reference, configure
from rhinestone.catalogs import BUILTIN
from rhinestone.models import SearchDiagnostic
from rhinestone.search import SearchResults

SPEC = importlib.util.spec_from_file_location(
    "worker", Path(__file__).parents[1] / "rhinestone_search/worker.py"
)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def resource(uri="https://example.org/data.json", format="geojson", **options):
    return configure().load(
        Reference("direct", parameters={"uri": uri, "format": format, **options})
    )


def test_search_preserves_selected_identity_and_diagnostics(monkeypatch):
    first, second = resource(), resource("https://example.org/second.json")
    unknown = resource("https://example.org/wms", "wms")
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
            "providers": [
                worker.ProviderId.SEARCH_CKAN_JP,
                worker.ProviderId.GEOSPATIAL_JP,
                worker.ProviderId.GSI,
            ],
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
        AccessPlan("file", "https://example.org/wms", "wms"),
        AccessPlan("file", "https://example.org/data.shp", "shapefile"),
        AccessPlan("file", "https://example.org/data", None),
        AccessPlan(
            "file", "https://example.org/data", "gpkg", options={"subdataset": "a"}
        ),
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
    "format",
    [
        "csv",
        "json",
        "gpkg",
        "flatgeobuf",
        "gml",
        "citygml",
        "kml",
        "geotiff",
        "cog",
        "netcdf",
    ],
)
def test_file_formats_are_downloaded_without_conversion(monkeypatch, tmp_path, format):
    body = b"opaque bytes interpreted only by the installed GDAL driver"
    monkeypatch.setattr(worker, "urlopen", lambda *a, **kw: Response(body))
    selected = resource(format=format)
    result = worker.execute(
        {
            "action": "download",
            "resource": selected.to_dict(),
            "target": str(tmp_path / "data"),
        }
    )
    path = Path(result["path"])
    assert path.read_bytes() == body
    assert path.suffix == worker.SUFFIXES[format]
    assert result["plan"] == selected.access_plan.to_dict()


def archive_bytes(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return stream.getvalue()


def download_archive(monkeypatch, tmp_path, entries, **options):
    monkeypatch.setattr(
        worker, "urlopen", lambda *a, **kw: Response(archive_bytes(entries))
    )
    selected = resource(format="zip")
    document = selected.to_dict()
    document["access_plan"]["options"].update(options)
    return worker.execute(
        {"action": "download", "resource": document, "target": str(tmp_path / "data")}
    )


def test_zip_preserves_all_layers_and_sidecars(monkeypatch, tmp_path):
    result = download_archive(
        monkeypatch,
        tmp_path,
        {
            "日本語/a.shp": b"shp",
            "日本語/a.dbf": b"dbf",
            "日本語/a.shx": b"shx",
            "b.geojson": b"{}",
        },
    )
    root = Path(result["path"])
    assert root.is_dir()
    assert (root / "日本語/a.dbf").read_bytes() == b"dbf"
    assert len(list(root.rglob("*.*"))) == 4


def test_zip_honors_entry_point_and_retains_sidecars(monkeypatch, tmp_path):
    result = download_archive(
        monkeypatch,
        tmp_path,
        {"a.shp": b"a", "a.dbf": b"b", "other.shp": b"c"},
        entry_point="a.shp",
    )
    assert Path(result["path"]).name == "a.shp"
    assert (Path(result["path"]).parent / "a.dbf").exists()


@pytest.mark.parametrize(
    "entries,options",
    [
        ({"../escape": b"a"}, {}),
        ({"C:/escape": b"a"}, {}),
        ({"a.shp": b"a", "A.SHP": b"b"}, {}),
        ({"a.shp": b"a"}, {"entry_point": "missing.shp"}),
    ],
)
def test_bad_archive_is_cleaned(monkeypatch, tmp_path, entries, options):
    with pytest.raises(worker.DownloadError):
        download_archive(monkeypatch, tmp_path, entries, **options)
    assert list(tmp_path.iterdir()) == []


def test_unpacked_size_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "MAX_UNPACKED_BYTES", 3)
    with pytest.raises(worker.DownloadError, match="展開上限"):
        download_archive(monkeypatch, tmp_path, {"a": b"1234"})
    assert list(tmp_path.iterdir()) == []


def test_size_limit_cleans_partial_file(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "MAX_BYTES", 3)
    monkeypatch.setattr(worker, "urlopen", lambda *a, **kw: Response(b"1234"))
    with pytest.raises(ValueError, match="512 MiB"):
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


def test_gsi_tile_search_and_open_does_not_download_pyramid(monkeypatch, tmp_path):
    selected = configure(catalog=BUILTIN).search(
        text="標準地図", providers=[worker.ProviderId.GSI]
    )[0]
    assert worker.unsupported(selected.access_plan) is None

    def unexpected(*args, **kwargs):
        pytest.fail("Tile pyramid must not be downloaded by Core worker")

    monkeypatch.setattr(worker, "urlopen", unexpected)
    result = worker.execute(
        {
            "action": "download",
            "resource": selected.to_dict(),
            "target": str(tmp_path / "unused"),
        }
    )
    assert result["tile"]["scheme"] == "xyz"
    assert result["tile"]["attribution"] == "国土地理院"
    assert result["plan"] == selected.access_plan.to_dict()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"scheme": "tms"},
        {"crs": "EPSG:4326"},
        {"min_zoom": -1},
        {"min_zoom": True},
        {"max_zoom": 1},
        {"format": "unknown"},
        {"url": "https://user:secret@example.org/{z}/{x}/{y}.png"},
        {"url": "https://example.org/tile.png"},
        {"tile_size": 512},
    ],
)
def test_invalid_tile_options_are_explained(changes):
    selected = configure(catalog=BUILTIN).search(
        text="標準地図", providers=[worker.ProviderId.GSI]
    )[0]
    tile = dict(selected.access_plan.options["tile"])
    tile.update(changes)
    assert worker.tile_problem(tile)


@pytest.mark.parametrize(
    "template,format",
    [
        ("https://other.example/{z}/{x}/{y}.png?token=a&b=c", "png"),
        ("https://other.example/%7Bz%7D/%7Bx%7D/%7By%7D.pbf", "pbf"),
        ("https://other.example/tiles?z={z}&x={x}&y={y}", "raster"),
    ],
)
def test_any_provider_xyz_template_is_recognized_without_filename_guess_for_files(
    template, format
):
    selected = resource(template, "unknown")
    plan = worker.plan_for(selected, configure())
    assert worker.unsupported(plan) is None
    assert plan.options["tile"]["format"] == format
    assert "min_zoom" not in plan.options["tile"]
    assert plan.uri == selected.uri
