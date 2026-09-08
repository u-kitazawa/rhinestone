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
    """冒頭例が外部検索に依存せず、明示したRuntimeで対応Resourceを開けることを保証する。"""

    class Dataset:
        width = 791
        height = 718
        count = 3

        def __enter__(self) -> "Dataset":
            return self

        def __exit__(
            self, exc_type: object, exc_value: object, traceback: object
        ) -> None:
            return None

    opened: list[str] = []
    runtime = ModuleType("rasterio")

    def open_dataset(uri: str) -> Dataset:
        opened.append(uri)
        return Dataset()

    runtime.open = open_dataset  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rasterio", runtime)

    source = documentation_python("index.md")
    exec(compile(source, "docs/index.md", "exec"), {})

    assert opened == [
        "https://raw.githubusercontent.com/rasterio/rasterio/"
        "57d9fda6c31c5595ea54262f905b43c5f8419e06/tests/data/RGB.byte.tif"
    ]
    assert capsys.readouterr().out == "791 x 718\nbands: 3\n"


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
