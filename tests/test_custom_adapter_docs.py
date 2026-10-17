"""Run the Source and Execution examples together as documented."""

import re
from pathlib import Path
from typing import Any


def test_custom_execution_example_opens_previously_loaded_resource() -> None:
    document = (Path(__file__).parents[1] / "docs" / "custom-adapters.md").read_text(
        encoding="utf-8"
    )
    sections = ("最小構成", "Execution Adapter（実行アダプター）")
    namespace: dict[str, Any] = {}
    calls: list[str] = []
    result = object()

    class Runtime:
        def read(self, uri: str) -> object:
            calls.append(uri)
            return result

    namespace["example_runtime"] = Runtime()
    for heading in sections:
        section = document.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
        source = re.findall(r"```python\n(.*?)\n```", section, re.DOTALL)[0]
        exec(compile(source, "docs/custom-adapters.md", "exec"), namespace)

    assert calls == ["https://data.example/items/example.geojson"]
    assert namespace["data"] is result
    assert namespace["resource"].reference.provider_id == "example"
