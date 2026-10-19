"""Exercise built-in Provider failures through the public search API."""

from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest

import rhinestone._http as http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Catalog, Provider, configure


@pytest.mark.parametrize(
    "adapter_type,settings",
    [
        ("ckan", {"endpoint": "https://fixture.example"}),
        ("geospatial-jp", {"endpoint": "https://fixture.example"}),
        ("plateau", {"endpoint": "https://fixture.example"}),
        ("search-ckan-jp", {"endpoint": "https://fixture.example"}),
        (
            "ogc-features",
            {"endpoint": "https://fixture.example", "collection_id": "rivers"},
        ),
        ("stac", {"endpoint": "https://fixture.example"}),
        ("stac", {"catalog_uri": "https://fixture.example/catalog.json"}),
        ("mlit-dpf", {"endpoint": "https://fixture.example", "credential": "fixture"}),
    ],
)
@pytest.mark.parametrize("failure_type", ["metadata", "response"])
def test_public_search_preserves_healthy_provider_after_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
    adapter_type: str,
    settings: dict[str, Any],
    failure_type: str,
) -> None:
    calls: list[str] = []

    def open_url(request: Any, *, timeout: int) -> BytesIO:
        calls.append(request.full_url)
        if failure_type == "metadata":
            raise OSError("fixture-secret")
        return BytesIO(b"{ fixture-secret")

    def build_opener(*handlers: object) -> SimpleNamespace:
        return SimpleNamespace(open=open_url)

    monkeypatch.setattr(http, "urlopen", open_url)
    monkeypatch.setattr(http, "build_opener", build_opener)
    app = configure(
        catalog=Catalog(
            (
                Provider("failing", adapter_type, settings),
                Provider(
                    "healthy",
                    "static",
                    {
                        "items": {
                            "fixture": {
                                "candidates": [
                                    {
                                        "uri": "https://healthy.example/data.geojson",
                                        "format": "geojson",
                                    }
                                ],
                                "metadata": {"title": "fixture"},
                            }
                        }
                    },
                ),
            )
        ),
        credentials={"fixture": lambda: "fixture-secret"},
    )

    results = app.search(text="fixture", bbox=(139, 35, 140, 36), limit=1)

    assert len(calls) == 1
    assert results.keys() == ("healthy",)
    assert [resource.uri for resource in results] == [
        "https://healthy.example/data.geojson"
    ]
    assert results[0].reference.provider_id == "healthy"
    failures = [d for d in results.diagnostics if d.reason == "provider_failure"]
    assert len(failures) == 1
    assert failures[0].source_id == "failing"
    assert failures[0].failure_type == failure_type
    assert "fixture-secret" not in repr(results.diagnostics)
    assert [(entry.source_id, entry.result_count) for entry in results.executions] == [
        ("failing", 0),
        ("healthy", 1),
    ]
