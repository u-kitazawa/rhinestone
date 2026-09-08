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


def test_documentation_index_example_opens_a_compatible_resource(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
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

    source = documentation_python("index.md")
    exec(compile(source, "docs/index.md", "exec"), {})

    assert len(opened) == 1
    assert "cyberjapandata.gsi.go.jp" in opened[0]
    output = capsys.readouterr().out
    assert output.startswith("URI: https://cyberjapandata.gsi.go.jp/")
    assert "raster size: 256 256\n" in output


def test_ckan_pyogrio_tutorial_registers_runtime() -> None:
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
    dependencies = next(
        keyword.value
        for keyword in configure_calls[0].keywords
        if keyword.arg == "dependencies"
    )
    assert isinstance(dependencies, ast.Dict)
    assert len(dependencies.keys) == 1
    key = dependencies.keys[0]
    assert isinstance(key, ast.Constant)
    assert key.value == "pyogrio"
    assert isinstance(dependencies.values[0], ast.Name)
    assert dependencies.values[0].id == "pyogrio"
