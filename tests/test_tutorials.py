import ast
from pathlib import Path


def tutorial_python(name: str) -> str:
    document = (Path(__file__).parents[1] / "docs" / "tutorials" / name).read_text(
        encoding="utf-8"
    )
    return document.split("```python\n", 1)[1].split("\n```", 1)[0]


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
