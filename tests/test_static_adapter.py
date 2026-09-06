from typing import Any, Mapping

import pytest

from rhinestone import Config, SearchQuery, SourceDefinition, configure
from rhinestone.adapters import StaticAdapter
from rhinestone.errors import (
    ConfigValidationError,
    ResourceNotFoundError,
    UnsupportedSearchConditionError,
)
from rhinestone.models import Source


def item(identifier: str = "one") -> Mapping[str, Any]:
    return {
        "metadata": {
            "title": identifier.title(),
            "description": "A static source",
            "publisher": "Test publisher",
            "raw": {"identifier": identifier, "checked": True},
        },
        "candidates": [
            {
                "uri": "https://example.test/" + identifier,
                "format": "geojson",
                "media_type": "application/geo+json",
                "attributes": {
                    "access_kind": "remote-dataset",
                    "access_options": {"kind": "test"},
                },
            }
        ],
        "capabilities": ["remote-dataset", "search"],
        "provenance": {
            "dataset_identifier": identifier,
            "original_url": "https://example.test/" + identifier,
        },
    }


def test_static_adapter_restores_source_and_provenance() -> None:
    adapter = StaticAdapter({"one": item()})

    source = adapter.load(Config("static", {"id": "one"}))

    assert isinstance(source, Source)
    assert source.metadata.title == "One"
    assert source.metadata.raw["checked"] is True
    assert source.candidates[0].uri.endswith("/one")
    assert source.provenance.dataset_identifier == "one"
    assert source.provenance.original_url.endswith("/one")


def test_static_adapter_search_is_deterministic_and_returns_configs() -> None:
    adapter = StaticAdapter({"z": item("z"), "a": item("a")})

    results = adapter.search(SearchQuery(text="a", limit=1))

    assert len(results) == 1
    assert results[0].to_config() == Config("static", {"id": "a"})


def test_static_adapter_rejects_unknown_and_unsupported_requests() -> None:
    adapter = StaticAdapter({"one": item()})

    with pytest.raises(ResourceNotFoundError):
        adapter.load(Config("static", {"id": "missing"}))
    with pytest.raises(UnsupportedSearchConditionError):
        adapter.search(SearchQuery(bbox=(0, 0, 1, 1)))
    with pytest.raises(ConfigValidationError):
        adapter.search(SearchQuery(limit=-1))


def test_static_source_composes_through_public_api() -> None:
    source = SourceDefinition("catalog", "static", {"items": {"one": item()}})
    app = configure(sources=(source,))

    resource = app.resolve(Config("catalog", {"id": "one"}))

    assert resource.provenance.provider == "catalog"
    assert resource.provenance.adapter == "static"
    assert resource.uri == "https://example.test/one"
