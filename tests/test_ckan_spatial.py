"""Opt-in spatial search for CKAN instances with ckanext-spatial."""

from collections.abc import Mapping
from typing import Any

import pytest

from rhinestone import Provider, configure
from rhinestone.adapters.source.ckan.adapter import CkanAdapter
from rhinestone.errors import ConfigValidationError
from rhinestone.models import SearchQuery


def test_spatial_ckan_sends_bbox_with_text_and_limit() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> Any:
        calls.append((url, dict(params)))
        return {"success": True, "result": {"results": [], "count": 0}}

    adapter = CkanAdapter(
        get_json, endpoint="https://example.test", spatial_search=True
    )

    assert adapter.search_conditions == frozenset({"text", "bbox", "format", "limit"})
    assert adapter.area_text_fallback is False
    assert (
        adapter.search(
            SearchQuery(text="river", bbox=(139.0, 35.0, 140.0, 36.0), limit=2)
        )
        == ()
    )
    assert calls == [
        (
            "https://example.test/api/3/action/package_search",
            {"q": "river", "ext_bbox": "139.0,35.0,140.0,36.0", "rows": 2},
        )
    ]


def test_spatial_ckan_projects_area_to_bbox(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        calls.append(dict(params))
        return {"success": True, "result": {"results": [], "count": 0}}

    monkeypatch.setattr("rhinestone._http.get_json", get_json)
    app = configure(
        sources=(
            Provider(
                "catalog",
                "ckan",
                {"endpoint": "https://example.test", "spatial_search": True},
            ),
        ),
    )
    results = app.search(text="river", area="神奈川県", limit=1)

    assert results.diagnostics == ()
    assert calls == [
        {
            "q": "river",
            "ext_bbox": "138.91582,35.1285,139.83493,35.67231",
            "rows": 1,
        }
    ]


def test_default_ckan_keeps_text_fallback_and_rejects_bbox() -> None:
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> Any:
        calls.append(dict(params))
        return {"success": True, "result": {"results": [], "count": 0}}

    adapter = CkanAdapter(get_json, endpoint="https://example.test")
    assert adapter.search_conditions == frozenset({"text", "format", "limit"})
    assert adapter.area_text_fallback is True
    with pytest.raises(ConfigValidationError, match="bbox"):
        adapter.search(SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0)))
    assert calls == []


@pytest.mark.parametrize("value", (1, "true", None))
def test_spatial_ckan_requires_explicit_boolean(value: object) -> None:
    with pytest.raises(ConfigValidationError, match="spatial_search"):
        configure(sources=(Provider("catalog", "ckan", {"spatial_search": value}),))
