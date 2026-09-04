import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple, cast

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_json(relative_path: str) -> Mapping[str, Any]:
    with (FIXTURES / relative_path).open(encoding="utf-8") as fixture:
        loaded = json.load(fixture)
    if not isinstance(loaded, dict):
        raise AssertionError("Provider fixture root must be an object")
    return cast(Dict[str, Any], loaded)


class RecordingJsonClient:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses = responses
        self.calls: List[Tuple[str, Mapping[str, Any]]] = []

    def __call__(self, url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((url, dict(params)))
        return self.responses[url]
