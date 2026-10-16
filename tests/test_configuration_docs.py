"""Execute configuration snippets without state from preceding code blocks."""

import re
from pathlib import Path
from typing import Any

import pytest

import rhinestone
from rhinestone import Rhinestone


def section_examples(heading: str) -> list[str]:
    document = (Path(__file__).parents[1] / "docs" / "configuration.md").read_text(
        encoding="utf-8"
    )
    section = document.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```python\n(.*?)\n```", section, re.DOTALL)


@pytest.mark.parametrize(
    "index,variable,credential",
    ((0, "ODPT_CONSUMER_KEY", "odpt"), (1, "STAC_TOKEN", "stac-token")),
)
def test_credential_examples_are_self_contained_and_lazy(
    monkeypatch: pytest.MonkeyPatch,
    index: int,
    variable: str,
    credential: str,
) -> None:
    source = section_examples("認証情報（Credential）")[index]
    actual_configure = rhinestone.configure
    calls: list[dict[str, Any]] = []

    def capture_configure(**kwargs: Any) -> Rhinestone:
        calls.append(kwargs)
        return actual_configure(**kwargs)

    monkeypatch.setattr(rhinestone, "configure", capture_configure)
    monkeypatch.delenv(variable, raising=False)
    namespace: dict[str, Any] = {}
    exec(compile(source, "docs/configuration.md", "exec"), namespace)

    assert isinstance(namespace["app"], Rhinestone)
    assert len(calls) == 1
    factory = calls[0]["credentials"][credential]
    monkeypatch.setenv(variable, "fixture-token")
    assert factory() == "fixture-token"
    monkeypatch.setenv(variable, "updated-fixture-token")
    assert factory() == "updated-fixture-token"


def test_adapter_registration_example_has_its_own_type_imports() -> None:
    source = section_examples("独自 Adapter を追加する")[0]
    namespace: dict[str, Any] = {}
    exec(compile(source, "docs/configuration.md", "exec"), namespace)

    assert isinstance(namespace["app"], Rhinestone)
