from typing import Any, Dict, List, Mapping, Optional, Tuple

import pytest

from rhinestone.adapters.execution.pyogrio import PyogrioAdapter
from rhinestone.adapters.source.direct import DirectAdapter
from rhinestone.adapters.source.search_ckan_jp import SearchCkanJpAdapter
from rhinestone.errors import (
    ConfigValidationError,
    ProviderResponseError,
    UnsupportedSourceError,
)
from rhinestone.models import Config, SearchQuery
from rhinestone.resolution import Resolver

from .provider_support import fixture_json


class RecordingJsonClient:
    def __init__(self, responses: Mapping[str, Any]) -> None:
        self.responses = dict(responses)
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def __call__(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        self.calls.append((url, dict(params)))
        return self.responses[url]


def test_search_ckan_jp_discovers_direct_resource_and_preserves_provenance() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    search_url = endpoint + "/package_search"
    client = RecordingJsonClient(
        {search_url: fixture_json("search_ckan_jp/package_search.json")}
    )
    adapter = SearchCkanJpAdapter(endpoint=endpoint, get_json=client)

    results = adapter.search(SearchQuery(text="river", limit=5))

    assert client.calls == [(search_url, {"q": "river", "rows": 5})]
    assert len(results) == 2
    result, second = results
    assert result.discovered_by == "search-ckan-jp"
    assert result.target == Config(
        "direct",
        {
            "uri": "https://catalog.example/dataset/original-dataset/resource/resource-1/download/rivers.geojson",
            "format": "geojson",
            "media_type": "application/geo+json",
            "metadata": {
                "title": "Example Rivers",
                "description": "Official river data",
                "publisher": "Example Municipality",
                "license": "CC BY 4.0",
                "raw": result.metadata.raw,
            },
        },
    )
    assert result.provenance.provider == "Example CKAN"
    assert result.provenance.dataset_identifier == "original-dataset"
    assert result.provenance.resource_identifier == "resource-1"
    assert result.provenance.original_url == (
        "https://catalog.example/dataset/original-dataset"
    )
    assert result.provenance.raw["resource"]["id"] == "resource-1"
    assert second.provenance.resource_identifier == "resource-2"
    assert second.target.settings["format"] == "csv"


def test_search_ckan_jp_limits_flattened_resources_and_preserves_unlimited_results() -> (
    None
):
    endpoint = "https://search.ckan.jp/backend/api"
    search_url = endpoint + "/package_search"
    client = RecordingJsonClient(
        {search_url: fixture_json("search_ckan_jp/package_search.json")}
    )
    adapter = SearchCkanJpAdapter(endpoint=endpoint, get_json=client)

    limited = adapter.search(SearchQuery(text="river", limit=1))
    unlimited = adapter.search(SearchQuery(text="river"))

    assert [result.provenance.resource_identifier for result in limited] == [
        "resource-1"
    ]
    assert [result.provenance.resource_identifier for result in unlimited] == [
        "resource-1",
        "resource-2",
    ]


def test_search_ckan_jp_is_discovery_only() -> None:
    adapter = SearchCkanJpAdapter(get_json=lambda url, params: {})

    with pytest.raises(UnsupportedSourceError, match="discovery-only"):
        adapter.load(Config("search-ckan-jp", {}))


def test_search_ckan_jp_requires_text() -> None:
    adapter = SearchCkanJpAdapter(get_json=lambda url, params: {})

    with pytest.raises(ConfigValidationError, match="text condition"):
        adapter.search(SearchQuery(limit=1))


def test_search_ckan_jp_handles_minimal_package_metadata() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    search_url = endpoint + "/package_search"
    client = RecordingJsonClient(
        {
            search_url: {
                "success": True,
                "result": {
                    "results": {
                        "id": "fallback-dataset",
                        "resources": {
                            "id": "zip-1",
                            "url": "https://data.example/archive.zip",
                            "mimetype": "application/zip",
                        },
                    }
                },
            }
        }
    )
    adapter = SearchCkanJpAdapter(endpoint=endpoint, get_json=client)

    results = adapter.search(SearchQuery(text="archive"))

    assert len(results) == 1
    assert results[0].title == "fallback-dataset"
    assert results[0].provenance.provider == "search-ckan-jp"
    assert results[0].target.settings["format"] == "zip"

    csv_results = adapter._package_results(  # pyright: ignore[reportPrivateUsage]
        {
            "title": "CSV dataset",
            "resources": {
                "id": "csv-1",
                "url": "https://data.example/data.csv",
                "format": "CSV",
            },
        },
        endpoint,
        {},
    )
    assert "media_type" not in csv_results[0].target.settings
    assert (
        adapter._package_results(  # pyright: ignore[reportPrivateUsage]
            {"resources": []}, endpoint, {}
        )
        == ()
    )


def test_search_ckan_jp_canonicalizes_geopackage_for_direct_resolution() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    result = SearchCkanJpAdapter(get_json=lambda url, params: None)._package_results(  # pyright: ignore[reportPrivateUsage]
        {
            "title": "GeoPackage dataset",
            "resources": {
                "id": "gpkg-1",
                "url": "https://data.example/data.gpkg",
                "format": "GeoPackage",
                "mimetype": "application/geopackage+sqlite3",
            },
        },
        endpoint,
        {"q": "gpkg"},
    )[0]

    assert result.target.settings["format"] == "gpkg"
    assert result.provenance.raw["resource"]["format"] == "GeoPackage"

    resource = Resolver().resolve(DirectAdapter().load(result.target))
    assert resource.format == "gpkg"
    assert PyogrioAdapter().supports(resource, frozenset({"pyogrio"}))


def test_search_ckan_jp_rejects_unsuccessful_response() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    client = RecordingJsonClient(
        {endpoint + "/package_search": {"success": False, "result": {}}}
    )
    adapter = SearchCkanJpAdapter(endpoint=endpoint, get_json=client)

    with pytest.raises(ProviderResponseError, match="not successful"):
        adapter.search(SearchQuery(text="archive"))
