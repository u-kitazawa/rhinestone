"""Execute the Runtime guide's explicit Reference-to-open example."""

import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def test_rasterio_recipe_loads_reference_and_supplies_runtime_at_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (Path(__file__).parents[1] / "docs" / "runtimes.md").read_text(
        encoding="utf-8"
    )
    section = document.split("### Rasterio\n", 1)[1].split("\n### ", 1)[0]
    source = re.findall(r"```python\n(.*?)\n```", section, re.DOTALL)[0]
    runtime = ModuleType("rasterio")
    opened: list[str] = []
    dataset = object()

    def open_raster(uri: str) -> object:
        opened.append(uri)
        return dataset

    runtime.open = open_raster  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "rasterio", runtime)
    namespace: dict[str, Any] = {}

    exec(compile(source, "docs/runtimes.md", "exec"), namespace)

    assert opened == ["https://example.invalid/data.tif"]
    assert namespace["dataset"] is dataset
    assert namespace["resource"].reference.provider_id == "direct"
    assert namespace["resource"].format == "geotiff"
