"""Keep valid CKAN-family distributions when one array member is malformed."""

from typing import Any

import pytest

import rhinestone._http as http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Catalog, Provider, configure


@pytest.mark.parametrize(
    "adapter_type", ["ckan", "geospatial-jp", "plateau", "search-ckan-jp"]
)
@pytest.mark.parametrize(
    "invalid_resource", [None, False, 1, "fixture-secret", [], [{}]]
)
def test_public_search_isolates_non_object_resources(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str, invalid_resource: object
) -> None:
    first = {
        "id": "first",
        "url": "https://data.example/first.csv",
        "format": "CSV",
    }
    second = {**first, "id": "second", "url": "https://data.example/second.csv"}
    package = {
        "id": "dataset",
        "title": "fixture",
        "resources": [first, invalid_resource, second],
    }

    def get_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True, "result": {"count": 1, "results": [package]}}

    monkeypatch.setattr(http, "get_json", get_json)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "catalog", adapter_type, {"endpoint": "https://catalog.example"}
                ),
            )
        )
    )

    results = app.search(text="fixture", limit=2)

    assert [r.reference.resource_identifier for r in results] == ["first", "second"]
    assert [r.uri for r in results] == [first["url"], second["url"]]
    assert all(r.metadata.title == "fixture" for r in results)
    assert [r.provenance.resource_identifier for r in results] == ["first", "second"]
    assert len(results.diagnostics) == 1
    diagnostic = results.diagnostics[0]
    assert diagnostic.source_id == "catalog"
    assert diagnostic.reason == "item_skipped"
    assert diagnostic.detail == "invalid_resource"
    assert diagnostic.resource_identifier is None
    assert "fixture-secret" not in repr(results.diagnostics)


@pytest.mark.parametrize(
    "adapter_type", ["ckan", "geospatial-jp", "plateau", "search-ckan-jp"]
)
@pytest.mark.parametrize("resources", [None, False, 1, "fixture-secret"])
def test_public_search_reports_broken_resource_containers(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str, resources: object
) -> None:
    def get_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "success": True,
            "result": {
                "count": 1,
                "results": [
                    {"id": "dataset", "title": "fixture", "resources": resources}
                ],
            },
        }

    monkeypatch.setattr(http, "get_json", get_json)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "catalog", adapter_type, {"endpoint": "https://catalog.example"}
                ),
            )
        )
    )

    results = app.search(text="fixture", limit=2)

    assert len(results) == 0
    assert len(results.diagnostics) == 1
    diagnostic = results.diagnostics[0]
    assert diagnostic.source_id == "catalog"
    assert diagnostic.reason == "provider_failure"
    assert diagnostic.failure_type == "response"
    assert "fixture-secret" not in repr(results.diagnostics)
