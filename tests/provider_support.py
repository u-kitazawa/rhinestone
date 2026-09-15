import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_json(relative_path: str) -> Mapping[str, Any]:
    with (FIXTURES / relative_path).open(encoding="utf-8") as fixture:
        loaded = json.load(fixture)
    if not isinstance(loaded, dict):
        raise AssertionError("Provider fixture root must be an object")
    return cast(dict[str, Any], loaded)


class RecordingJsonClient:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def __call__(self, url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((url, dict(params)))
        return self.responses[url]


class ResponseJsonClient(RecordingJsonClient):
    def __init__(
        self,
        responses: Mapping[str, Mapping[str, Any]],
        response_uris: Mapping[str, str],
    ) -> None:
        super().__init__(responses)
        self.response_uris = response_uris

    def __call__(self, url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        response = dict(super().__call__(url, params))
        return _ResponseMapping(response, self.response_uris[url])


class _ResponseMapping(dict[str, Any]):
    def __init__(self, value: Mapping[str, Any], response_uri: str) -> None:
        super().__init__(value)
        self.response_uri = response_uri
