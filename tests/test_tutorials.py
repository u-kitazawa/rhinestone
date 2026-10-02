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
