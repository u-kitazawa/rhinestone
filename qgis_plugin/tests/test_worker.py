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
from rhinestone.models import SearchDiagnostic, SearchQuery
from rhinestone.search import SearchResults

SPEC = importlib.util.spec_from_file_location(
    "worker", Path(__file__).parents[1] / "rhinestone_search/worker.py"
)
worker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker)


def conditions(text="公園", **values):
    return {
        "text": text,
        "limit": 20,
        "providers": [
            worker.ProviderId.SEARCH_CKAN_JP,
            worker.ProviderId.GEOSPATIAL_JP,
            worker.ProviderId.GSI,
        ],
        **values,
    }


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

    def search(query):
        assert query == SearchQuery(
            **{
                "providers": [
                    worker.ProviderId.SEARCH_CKAN_JP,
                    worker.ProviderId.GEOSPATIAL_JP,
                    worker.ProviderId.GSI,
                ],
                "text": "公園",
                "limit": 20,
            }
        )
        return SearchResults.from_grouped(
            {"test": (unknown, first, second)}, diagnostics
        )

    monkeypatch.setattr(worker, "search", search)
    result = worker.execute({"action": "search", "conditions": conditions()})
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


def test_large_zip_manifest_is_not_rejected_by_size(monkeypatch, tmp_path):
    original = zipfile.ZipFile.infolist

    def large_manifest(archive):
        from copy import copy

        members = [copy(member) for member in original(archive)]
        for member in members:
            member.file_size = 1024 * 1024 * 1024 + 1
        return members

    # Keep extraction real while simulating a large central-directory size.
    extract = zipfile.ZipFile.extract
    monkeypatch.setattr(zipfile.ZipFile, "infolist", large_manifest)
    monkeypatch.setattr(
        zipfile.ZipFile,
        "extract",
        lambda archive, member, path: extract(archive, member.filename, path),
    )
    result = download_archive(monkeypatch, tmp_path, {"a.csv": b"a,b\n1,2"})
    assert (Path(result["path"]) / "a.csv").read_bytes() == b"a,b\n1,2"


def test_download_over_previous_limit_reads_bounded_chunks(monkeypatch, tmp_path):
    class LargeResponse(Response):
        remaining = 513 * 1024 * 1024

        def read(self, size=-1):
            assert 0 < size <= 65536
            count = min(size, self.remaining)
            self.remaining -= count
            return b"x" * count

    monkeypatch.setattr(worker, "urlopen", lambda *a, **kw: LargeResponse())
    result = worker.execute(
        {
            "action": "download",
            "resource": resource().to_dict(),
            "target": str(tmp_path / "data.geojson"),
        }
    )
    assert Path(result["path"]).stat().st_size == 513 * 1024 * 1024
    assert not list(tmp_path.glob("*.part"))


def test_zip_entry_limit_cleans_download(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "MAX_MEMBERS", 1)
    with pytest.raises(worker.DownloadError, match="エントリー上限"):
        download_archive(monkeypatch, tmp_path, {"a": b"a", "b": b"b"})
    assert list(tmp_path.iterdir()) == []


def test_disk_full_during_download_cleans_partial_file(monkeypatch, tmp_path):
    original = Path.open

    class FullDisk(io.BytesIO):
        def write(self, data):
            raise OSError(28, "No space left on device")

    def open_file(path, mode="r", *args, **kwargs):
        if mode == "xb":
            path.touch()
            return FullDisk()
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(worker, "urlopen", lambda *a, **kw: Response(b"1234"))
    with pytest.raises(worker.DownloadError, match="空き容量"):
        worker.execute(
            {
                "action": "download",
                "resource": resource().to_dict(),
                "target": str(tmp_path / "data.geojson"),
            }
        )
    assert list(tmp_path.iterdir()) == []


def test_disk_full_during_extraction_cleans_all_files(monkeypatch, tmp_path):
    def extract(archive, member, directory):
        (directory / member.filename).write_bytes(b"partial")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(zipfile.ZipFile, "extract", extract)
    with pytest.raises(worker.DownloadError, match="空き容量"):
        download_archive(monkeypatch, tmp_path, {"a.csv": b"a,b"})
    assert list(tmp_path.iterdir()) == []


def test_main_sanitizes_network_failure(monkeypatch, capsys):
    monkeypatch.setattr(
        worker.sys,
        "stdin",
        io.StringIO(json.dumps({"action": "search", "conditions": conditions()})),
    )

    def fail(*args, **kwargs):
        raise OSError("https://secret@example.org/private")

    monkeypatch.setattr(worker, "search", fail)
    worker.main()
    assert json.loads(capsys.readouterr().out) == {"ok": False, "error": "OSError"}


def test_planning_failure_is_disabled(monkeypatch):
    monkeypatch.setattr(
        worker, "search", lambda *args, **kw: SearchResults({"test": (resource(),)})
    )

    def fail(value):
        raise ValueError("bad plan")

    monkeypatch.setattr(worker, "configure", lambda: SimpleNamespace(plan=fail))
    assert (
        "ValueError"
        in worker.execute({"action": "search", "conditions": conditions()})["rows"][0][
            "reason"
        ]
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


def test_catalog_exposes_all_builtin_providers_and_search_formats():
    result = worker.execute({"action": "catalog"})
    assert {p["id"] for p in result["providers"]} == {p.id for p in BUILTIN}
    assert any(
        p["id"] == worker.ProviderId.GSI and p["default"] for p in result["providers"]
    )
    assert "geojson" in {f["id"] for f in result["formats"]}
    assert not next(
        p for p in result["providers"] if p["id"] == worker.ProviderId.ODPT
    )["searchable"]


def test_search_forwards_area_formats_time_limit_and_selected_providers(monkeypatch):
    from datetime import datetime

    from rhinestone import Format

    captured = []

    def search(query):
        captured.append(query)
        return SearchResults({})

    monkeypatch.setattr(worker, "search", search)
    worker.execute(
        {
            "action": "search",
            "conditions": conditions(
                None,
                area="横浜市",
                format=["geojson", "gpkg"],
                time=["2026-01-01T00:00:00+09:00", None],
                limit=7,
                providers=[worker.ProviderId.GEOSPATIAL_JP],
            ),
        }
    )
    assert captured == [
        SearchQuery(
            text=None,
            area="横浜市",
            format=(Format.GEOJSON, Format.GPKG),
            time=(datetime.fromisoformat("2026-01-01T00:00:00+09:00"), None),
            limit=7,
            providers=[worker.ProviderId.GEOSPATIAL_JP],
        )
    ]


@pytest.mark.parametrize(
    "values",
    [
        {"area": "横浜市", "bbox": [138, 35, 140, 37]},
        {"bbox": [138, 35, 140]},
        {"time": ["not-a-date", None]},
        {"time": ["2026-01-02", "2026-01-01"]},
        {"format": ["not-a-format"]},
        {"bbox": [float("nan"), 35, 140, 37]},
    ],
)
def test_invalid_search_conditions_fail_before_network(monkeypatch, values):
    def fail(*args, **kwargs):
        pytest.fail("Invalid conditions must not reach the provider search")

    monkeypatch.setattr(worker, "search", fail)
    with pytest.raises(worker.DownloadError, match="検索条件"):
        worker.execute({"action": "search", "conditions": conditions(**values)})


def test_bbox_and_open_ended_time_are_converted_without_guessing():
    query = worker.search_conditions(
        conditions(
            None,
            bbox=[138, 35, 140, 37],
            time=[None, "2026-01-01T00:00:00Z"],
            limit=None,
        )
    )
    assert query.bbox == (138, 35, 140, 37)
    assert query.time[0] is None
    assert query.time[1].utcoffset().total_seconds() == 0
    assert query.limit is None


def test_search_injects_only_selected_provider_credentials(monkeypatch):
    captured = []

    def configured(**kwargs):
        captured.append(kwargs["credentials"])
        return SimpleNamespace(search=lambda query: SearchResults({}))

    monkeypatch.setattr(worker, "configure", configured)
    result = worker.execute(
        {
            "action": "search",
            "conditions": conditions(providers=["mlit-dpf"]),
            "credentials": {"mlit-dpf": "private-key", "unused": "other-secret"},
        }
    )
    assert set(captured[0]) == {"mlit-dpf"}
    assert captured[0]["mlit-dpf"]() == "private-key"
    assert "private-key" not in json.dumps(result)
    assert "other-secret" not in json.dumps(result)


def test_unselected_credentials_are_not_configured(monkeypatch):
    monkeypatch.setattr(worker, "search", lambda query: SearchResults({}))
    monkeypatch.setattr(worker, "configure", lambda: SimpleNamespace())
    assert worker.execute(
        {
            "action": "search",
            "conditions": conditions(),
            "credentials": {"mlit-dpf": "unused-secret"},
        }
    ) == {"rows": [], "diagnostics": []}


def test_dpf_search_uses_key_in_header_without_serializing_it(monkeypatch):
    import rhinestone._http as http

    calls = []

    def post(url, body, headers=None):
        calls.append((url, headers))
        return {"data": {"search": {"totalNumber": 0, "searchResults": []}}}

    monkeypatch.setattr(http, "post_json", post)
    result = worker.execute(
        {
            "action": "search",
            "conditions": conditions(providers=["mlit-dpf"]),
            "credentials": {"mlit-dpf": "fixture-api-key"},
        }
    )
    assert calls
    assert all(
        url == "https://data-platform.mlit.go.jp/api/v1"
        and headers == {"apikey": "fixture-api-key"}
        for url, headers in calls
    )
    assert result == {"rows": [], "diagnostics": []}


@pytest.mark.parametrize("values", [[], {"name": 1}, {"": "secret"}, {"key": ""}])
def test_invalid_credentials_do_not_echo_values(values):
    with pytest.raises(worker.DownloadError, match="認証情報") as error:
        worker.execute(
            {"action": "search", "conditions": conditions(), "credentials": values}
        )
    assert "secret" not in str(error.value)
