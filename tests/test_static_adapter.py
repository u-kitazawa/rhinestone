from types import SimpleNamespace
from typing import Any, Dict, Mapping, Tuple, cast
from xml.etree.ElementTree import fromstring

import pytest

from rhinestone import Config, SearchQuery, SourceDefinition, configure, sources
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
    assert source.provenance.original_url == "https://example.test/one"


def test_static_adapter_search_is_deterministic_and_returns_configs() -> None:
    adapter = StaticAdapter({"z": item("z"), "a": item("a")})

    results = adapter.search(SearchQuery(text="a", limit=1))

    assert len(results) == 1
    assert results[0].to_config() == Config("static", {"id": "a"})
    assert adapter.search(SearchQuery(text="absent")) == ()


def test_static_adapter_rejects_unknown_and_unsupported_requests() -> None:
    adapter = StaticAdapter({"one": item()})

    with pytest.raises(ResourceNotFoundError):
        adapter.load(Config("static", {"id": "missing"}))
    with pytest.raises(UnsupportedSearchConditionError):
        adapter.search(SearchQuery(bbox=(0, 0, 1, 1)))
    with pytest.raises(ConfigValidationError):
        adapter.search(SearchQuery(limit=-1))


def test_static_adapter_rejects_invalid_catalog() -> None:
    invalid_items: Tuple[object, ...] = (
        {},
        [],
        {"": item()},
        {"one": []},
        {"one": {"metadata": []}},
        {"one": {"candidates": []}},
        {"one": {"candidates": [{}]}},
        {"one": {"candidates": [{"uri": "https://example.test", "format": 1}]}},
        {"one": {"candidates": [{"uri": "https://example.test", "media_type": 1}]}},
        {"one": {"candidates": [{"uri": "https://example.test", "attributes": []}]}},
        {"one": {"capabilities": []}},
        {"one": {"capabilities": [1]}},
        {"one": {"provenance": []}},
    )
    for items in invalid_items:
        with pytest.raises(ConfigValidationError):
            StaticAdapter(cast(Any, items))


def test_static_adapter_rejects_invalid_candidate_shapes() -> None:
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": {"candidates": [1]}})
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": {"candidates": [{"uri": ""}]}})


def test_static_adapter_rejects_invalid_metadata_and_query_parameters() -> None:
    metadata_item = dict(item())
    metadata_item["metadata"] = dict(metadata_item["metadata"])
    metadata_item["metadata"]["raw"] = []
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": metadata_item}).load(Config("static", {"id": "one"}))

    query_item = dict(item())
    query_item["provenance"] = {"query_parameters": []}
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": query_item}).load(Config("static", {"id": "one"}))


def test_builtin_gsi_tiles_are_static_catalog_items() -> None:
    captured: Dict[str, Any] = {}

    def open_ex(uri: str, **kwargs: Any) -> str:
        captured["uri"] = uri
        return "dataset"

    app = configure(
        sources=(sources.GSI,),
        dependencies={"gdal": lambda: SimpleNamespace(OpenEx=open_ex)},
    )
    resource = app.resolve(Config("gsi", {"id": "std"}))

    assert resource.access_plan.kind == "remote-dataset"
    assert resource.format == "png"
    assert resource.metadata.raw["attribution"] == "国土地理院"
    assert resource.open() == "dataset"
    xml = fromstring(captured["uri"])
    assert xml.findtext("DataWindow/YOrigin") == "top"
    assert "${z}/${x}/${y}.png" in cast(str, xml.findtext("Service/ServerUrl"))


def test_static_source_composes_through_public_api() -> None:
    source = SourceDefinition("catalog", "static", {"items": {"one": item()}})
    app = configure(sources=(source,))

    resource = app.resolve(Config("catalog", {"id": "one"}))

    assert resource.provenance.provider == "catalog"
    assert resource.provenance.adapter == "static"
    assert resource.uri == "https://example.test/one"


def test_static_source_requires_items_in_composition() -> None:
    with pytest.raises(ConfigValidationError, match="requires items"):
        configure(sources=(SourceDefinition("catalog", "static"),))


def test_static_adapter_validates_capabilities_and_provenance_objects() -> None:
    invalid_capabilities = dict(item())
    invalid_capabilities["capabilities"] = 1
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": invalid_capabilities})

    invalid_capability = dict(item())
    invalid_capability["capabilities"] = [1]
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": invalid_capability})

    invalid_provenance = dict(item())
    invalid_provenance["provenance"] = []
    with pytest.raises(ConfigValidationError):
        StaticAdapter({"one": invalid_provenance})
