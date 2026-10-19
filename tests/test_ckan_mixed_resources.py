"""Keep valid CKAN-family distributions when one array member is malformed."""

from collections.abc import Mapping
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
@pytest.mark.parametrize(
    "invalid_package", [None, False, 1, "fixture-secret", [], [{}]]
)
def test_public_search_isolates_packages_and_pages_by_received_count(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str, invalid_package: object
) -> None:
    def package(identifier: str) -> dict[str, Any]:
        return {
            "id": identifier,
            "title": identifier,
            "resources": [
                {
                    "id": identifier,
                    "url": f"https://data.example/{identifier}.csv",
                    "format": "CSV",
                }
            ],
        }

    starts: list[int] = []

    def get_json(
        url: str, params: Mapping[str, Any], *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        start = params.get("start", 0)
        starts.append(start)
        if start == 0:
            packages = [package("first"), invalid_package]
        elif start == 2:
            packages = [package("second")]
        else:
            pytest.fail(f"unexpected page offset {start}")
        return {"success": True, "result": {"count": 3, "results": packages}}

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
    assert starts == [0, 2]
    assert len(results.diagnostics) == 1
    diagnostic = results.diagnostics[0]
    assert diagnostic.source_id == "catalog"
    assert diagnostic.reason == "item_skipped"
    assert diagnostic.detail == "invalid_dataset"
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


@pytest.mark.parametrize(
    "adapter_type", ["ckan", "geospatial-jp", "plateau", "search-ckan-jp"]
)
@pytest.mark.parametrize("resources", [[], [None]])
def test_empty_or_invalid_distributions_do_not_stop_next_page(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str, resources: list[object]
) -> None:
    starts: list[int] = []

    def get_json(
        url: str, params: Mapping[str, Any], *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        start = params.get("start", 0)
        starts.append(start)
        return {
            "success": True,
            "result": {
                "count": 2,
                "results": [
                    {
                        "id": "empty" if start == 0 else "healthy",
                        "title": "fixture",
                        "resources": resources
                        if start == 0
                        else [
                            {
                                "id": "healthy",
                                "format": "CSV",
                                "url": "https://data.example/healthy.csv",
                            }
                        ],
                    }
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

    results = app.search(text="fixture", limit=1)

    assert [r.reference.resource_identifier for r in results] == ["healthy"]
    assert starts == [0, 1]
    assert [d.detail for d in results.diagnostics] == (
        ["invalid_resource"] if resources else []
    )


@pytest.mark.parametrize(
    "adapter_type", ["ckan", "geospatial-jp", "plateau", "search-ckan-jp"]
)
@pytest.mark.parametrize(
    "packages", [None, False, 1, "fixture-secret", {"id": "empty", "resources": []}]
)
def test_package_container_validation_preserves_single_object_contract(
    monkeypatch: pytest.MonkeyPatch, adapter_type: str, packages: object
) -> None:
    def get_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True, "result": {"count": 1, "results": packages}}

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

    results = app.search(text="fixture", limit=1)

    assert len(results) == 0
    assert [d.reason for d in results.diagnostics] == (
        [] if isinstance(packages, dict) else ["provider_failure"]
    )
    assert all(d.failure_type == "response" for d in results.diagnostics)
    assert "fixture-secret" not in repr(results.diagnostics)
