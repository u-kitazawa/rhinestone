import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest


def documentation_python(name: str) -> str:
    document = (Path(__file__).parents[1] / "docs" / name).read_text(encoding="utf-8")
    return document.split("```python\n", 1)[1].split("\n```", 1)[0]


def tutorial_python(name: str) -> str:
    return documentation_python(f"tutorials/{name}")


@pytest.mark.parametrize("reverse_catalog", (False, True))
def test_documentation_index_example_opens_a_compatible_resource(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    reverse_catalog: bool,
) -> None:
    """冒頭例が決定的な検索結果を明示Runtimeで開けることを保証する。"""

    class Dataset:
        RasterXSize = 256
        RasterYSize = 256

    opened: list[str] = []
    gdal = ModuleType("osgeo.gdal")

    def open_ex(uri: str, **kwargs: object) -> Dataset:
        opened.append(uri)
        return Dataset()

    gdal.OpenEx = open_ex  # type: ignore[attr-defined]
    osgeo = ModuleType("osgeo")
    osgeo.gdal = gdal  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "osgeo", osgeo)
    monkeypatch.setitem(sys.modules, "osgeo.gdal", gdal)

    if reverse_catalog:
        import rhinestone.catalogs as catalogs

        monkeypatch.setattr(
            catalogs, "BUILTIN", catalogs.Catalog(reversed(catalogs.BUILTIN))
        )

    source = documentation_python("index.md")
    exec(compile(source, "docs/index.md", "exec"), {})

    assert len(opened) == 1
    assert "cyberjapandata.gsi.go.jp" in opened[0]
    output = capsys.readouterr().out
    assert output.startswith("URI: https://cyberjapandata.gsi.go.jp/")
    assert "raster size: 256 256\n" in output


def test_ckan_pyogrio_tutorial_passes_runtime_at_open() -> None:
    source = tutorial_python("ckan-pyogrio.md")
    tree = ast.parse(source)
    configure_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "configure"
    ]

    assert len(configure_calls) == 1
    assert not any(
        keyword.arg == "dependencies" for keyword in configure_calls[0].keywords
    )
    open_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "open"
    ]
    assert any(
        any(
            keyword.arg == "runtime"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "pyogrio"
            for keyword in call.keywords
        )
        for call in open_calls
    )


def test_ckan_pyogrio_tutorial_filters_formats_before_opening(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CSVのpageを飛ばし、後続のベクター配布物を解決して開ける。"""
    from rhinestone import api

    csv_resource = {
        "id": "table",
        "url": "https://assets.example/table.csv",
        "format": "CSV",
    }
    vector_resource = {
        "id": "vector",
        "package_id": "vector-package",
        "url": "https://assets.example/vector.gpkg",
        "format": "GeoPackage",
    }
    package = {
        "id": "vector-package",
        "title": "河川",
        "resources": [vector_resource],
    }
    search_params: list[dict[str, object]] = []

    def get_json(
        url: str, params: dict[str, object], headers: object = None
    ) -> dict[str, object]:
        if url.endswith("/package_search"):
            search_params.append(dict(params))
            return {
                "success": True,
                "result": {
                    "count": 2,
                    "results": [
                        package
                        if params.get("start") == 1
                        else {
                            "id": "table-package",
                            "title": "河川",
                            "resources": [csv_resource],
                        }
                    ],
                },
            }
        if url.endswith("/resource_show"):
            assert params == {"id": "vector"}
            return {"success": True, "result": vector_resource}
        assert url.endswith("/package_show")
        assert params == {"id": "vector-package"}
        return {"success": True, "result": package}

    class Frame:
        columns = ("geometry", "name")

        def __len__(self) -> int:
            return 1

    opened: list[str] = []
    pyogrio = ModuleType("pyogrio")

    def read_dataframe(uri: str, **kwargs: object) -> Frame:
        opened.append(uri)
        return Frame()

    pyogrio.read_dataframe = read_dataframe  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyogrio", pyogrio)
    monkeypatch.setattr(getattr(api, "_http"), "get_json", get_json)
    monkeypatch.setenv("RHINESTONE_CKAN_QUERY", "河川")
    monkeypatch.setenv("RHINESTONE_CKAN_RESULT_INDEX", "0")

    source = tutorial_python("ckan-pyogrio.md")
    exec(compile(source, "docs/tutorials/ckan-pyogrio.md", "exec"), {})

    assert search_params == [
        {"q": "(title_string:*河川* OR tags:*河川*)", "rows": 100, "start": 0},
        {"q": "(title_string:*河川* OR tags:*河川*)", "rows": 100, "start": 1},
    ]
    assert opened == ["https://assets.example/vector.gpkg"]
    output = capsys.readouterr().out
    assert "formats: ['gpkg']" in output
    assert "format: gpkg\n" in output
    assert "rows: 1\n" in output


def test_stac_rasterio_tutorial_selects_an_explicit_asset(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """複数data assetでも明示keyで選択し、検索前提にしないことを保証する。"""

    class Dataset:
        width = 1024
        height = 512
        count = 3

        def __enter__(self) -> "Dataset":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    opened: list[str] = []
    rasterio = ModuleType("rasterio")

    def open_dataset(uri: str, **kwargs: object) -> Dataset:
        opened.append(uri)
        return Dataset()

    rasterio.open = open_dataset  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rasterio", rasterio)
    monkeypatch.setenv("RHINESTONE_STAC_ENDPOINT", "https://stac.example/api")
    monkeypatch.setenv("RHINESTONE_STAC_COLLECTION_ID", "imagery")
    monkeypatch.setenv("RHINESTONE_STAC_ITEM_ID", "scene-1")
    monkeypatch.setenv("RHINESTONE_STAC_ASSET_KEY", "visual")

    from rhinestone import api

    requested: list[tuple[str, object]] = []

    def get_json(url: str, params: object, headers: object = None) -> dict[str, object]:
        requested.append((url, params))
        return {
            "id": "scene-1",
            "collection": "imagery",
            "properties": {"title": "Scene 1"},
            "assets": {
                "analytic": {
                    "href": "https://assets.example/analytic.tif",
                    "roles": ["data"],
                    "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                },
                "visual": {
                    "href": "https://assets.example/visual.tif",
                    "roles": ["data"],
                    "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                },
            },
        }

    monkeypatch.setattr(getattr(api, "_http"), "get_json", get_json)

    source = tutorial_python("stac-rasterio.md")
    exec(compile(source, "docs/tutorials/stac-rasterio.md", "exec"), {})

    assert requested == [
        (
            "https://stac.example/api/collections/imagery/items/scene-1",
            {},
        )
    ]
    assert opened == ["https://assets.example/visual.tif"]
    output = capsys.readouterr().out
    assert "resource: https://assets.example/visual.tif\n" in output
    assert "format: cog\n" in output
    assert "width x height: 1024 x 512\n" in output
    assert "bands: 3\n" in output
