"""Run the Source and Execution examples together as documented."""

import re
from pathlib import Path
from typing import Any

import pytest


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


def test_custom_auth_example_authorizes_before_loading_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rhinestone import Catalog, Provider, _http, configure
    from rhinestone.adapters.contracts import SourceAdapterDefinition
    from rhinestone.errors import DestinationNotAllowedError

    document = (Path(__file__).parents[1] / "docs" / "custom-adapters.md").read_text(
        encoding="utf-8"
    )
    source = next(
        block
        for block in re.findall(r"```python\n(.*?)\n```", document, re.DOTALL)
        if "def authenticated_document(" in block
    )
    namespace: dict[str, Any] = {}
    exec(compile(source, "docs/custom-adapters.md", "exec"), namespace)
    contexts: list[Any] = []

    def factory(provider: Provider, context: Any) -> Any:
        contexts.append(context)
        return object()

    provider = Provider(
        "custom",
        "custom-source",
        {"endpoint": "https://custom.example/api", "credential": "custom-api-key"},
    )
    credential_calls: list[bool] = []

    def credential() -> str:
        credential_calls.append(True)
        return "fixture-secret"

    configure(
        catalog=Catalog((provider,)),
        adapters=(SourceAdapterDefinition("custom-source", factory),),
        credentials={"custom-api-key": credential},
    )
    requests: list[str] = []

    def get_text(url: str, headers: Any = None) -> str:
        assert headers == {
            "Accept": "text/turtle",
            "Authorization": "Bearer fixture-secret",
        }
        requests.append(url)
        return "fixture document"

    monkeypatch.setattr(_http, "get_text", get_text)
    fetch = namespace["authenticated_document"]
    with pytest.raises(DestinationNotAllowedError):
        fetch(provider, contexts[0], "https://untrusted.example/api")
    assert credential_calls == []
    assert requests == []
    assert fetch(provider, contexts[0], "https://custom.example/api/catalog") == (
        "fixture document"
    )
    assert credential_calls == [True]
    assert requests == ["https://custom.example/api/catalog"]
    assert "fixture-secret" not in repr(provider)
