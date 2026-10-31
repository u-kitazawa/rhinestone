"""Execute the documented caller-owned Range runtime with real pipeline/Plan APIs."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rhinestone import Reference, configure

URI = "https://data.example/selected.tif"


def test_documented_range_runtime_keeps_plan_uri_and_uses_independent_receiver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def open_ex(uri: str, **options: Any) -> Any:
        calls.append((uri, options))
        return SimpleNamespace(RasterXSize=900, RasterYSize=900)

    monkeypatch.setitem(
        sys.modules, "osgeo", SimpleNamespace(gdal=SimpleNamespace(OpenEx=open_ex))
    )
    resource = configure().load(
        Reference("direct", parameters={"uri": URI, "format": "cog"})
    )
    path = Path(__file__).parents[1] / "docs/api/adapters/gdal.md"
    code = path.read_text().split("```python\n", 1)[1].split("```", 1)[0]
    namespace: dict[str, Any] = {"resource": resource}
    exec(compile(code, str(path), "exec"), namespace)

    assert calls == [("/vsicurl/" + URI, {"open_options": ()})] * 2
    assert resource.uri == URI
    assert namespace["received_plan"].uri == URI
    assert json.loads(namespace["plan_json"])["uri"] == URI
    with pytest.raises(ValueError, match="許可"):
        namespace["open_with_ranges"]("https://data.example/other.tif")
    assert len(calls) == 2
