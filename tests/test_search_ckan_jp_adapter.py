from collections.abc import Mapping
from typing import Any

import pytest

from rhinestone import Format
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
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
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

    assert client.calls == [
        (
            search_url,
            {
                "q": '(xckan_title:"river"^8 OR xckan_title:*river*^4 OR "river")',
                "rows": 10,
            },
        )
    ]
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


def test_search_ckan_jp_pages_packages_until_the_resource_limit_is_met() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        assert url == endpoint + "/package_search"
        calls.append(dict(params))
        package: dict[str, Any]
        if params.get("start") is None:
            package = {"id": "empty", "resources": []}
        else:
            package = {
                "id": "next",
                "title": "Next page",
                "resources": [
                    {
                        "id": "resource-1",
                        "url": "https://data.example/next.csv",
                        "format": "CSV",
                    }
                ],
            }
        return {"success": True, "result": {"count": 2, "results": [package]}}

    results = SearchCkanJpAdapter(endpoint=endpoint, get_json=get_json).search(
        SearchQuery(text="river", limit=1)
    )

    assert [result.provenance.resource_identifier for result in results] == [
        "resource-1"
    ]
    assert calls == [
        {
            "q": '(xckan_title:"river"^8 OR xckan_title:*river*^4 OR "river")',
            "rows": 10,
        },
        {
            "q": '(xckan_title:"river"^8 OR xckan_title:*river*^4 OR "river")',
            "rows": 10,
            "start": 1,
        },
    ]


def test_search_ckan_jp_continues_after_a_server_capped_partial_package_page() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        assert url == endpoint + "/package_search"
        calls.append(dict(params))
        start = params.get("start", 0)
        package: dict[str, Any] = {
            "id": f"package-{start}",
            "title": f"Package {start}",
            "resources": [],
        }
        if start:
            package["resources"] = [
                {
                    "id": f"resource-{start}",
                    "url": f"https://data.example/{start}.csv",
                    "format": "CSV",
                }
            ]
        return {"success": True, "result": {"count": 3, "results": [package]}}

    results = SearchCkanJpAdapter(endpoint=endpoint, get_json=get_json).search(
        SearchQuery(text="river", limit=2)
    )

    assert [result.provenance.resource_identifier for result in results] == [
        "resource-1",
        "resource-2",
    ]
    assert [call.get("start", 0) for call in calls] == [0, 1, 2]


def test_search_ckan_jp_zero_limit_skips_requests_and_stops_at_known_last_page() -> (
    None
):
    adapter = SearchCkanJpAdapter(
        endpoint="https://search.ckan.jp/backend/api",
        get_json=lambda url, params: pytest.fail("zero limit must not request"),
    )
    assert adapter.search(SearchQuery(text="river", limit=0)) == ()

    client = RecordingJsonClient(
        {
            "https://search.ckan.jp/backend/api/package_search": {
                "success": True,
                "result": {"count": 1, "results": [{"id": "empty", "resources": []}]},
            }
        }
    )
    assert (
        SearchCkanJpAdapter(
            endpoint="https://search.ckan.jp/backend/api", get_json=client
        ).search(SearchQuery(text="river", limit=1))
        == ()
    )
    assert len(client.calls) == 1


def test_search_ckan_jp_rejects_an_invalid_count_before_paging() -> None:
    client = RecordingJsonClient(
        {
            "https://search.ckan.jp/backend/api/package_search": {
                "success": True,
                "result": {
                    "count": "unknown",
                    "results": [{"id": "empty", "resources": []}],
                },
            }
        }
    )

    with pytest.raises(ProviderResponseError, match="count"):
        SearchCkanJpAdapter(
            endpoint="https://search.ckan.jp/backend/api", get_json=client
        ).search(SearchQuery(text="river", limit=1))


def test_search_ckan_jp_rejects_an_empty_page_before_its_declared_count() -> None:
    client = RecordingJsonClient(
        {
            "https://search.ckan.jp/backend/api/package_search": {
                "success": True,
                "result": {"count": 1, "results": []},
            }
        }
    )

    with pytest.raises(ProviderResponseError, match="empty"):
        SearchCkanJpAdapter(
            endpoint="https://search.ckan.jp/backend/api", get_json=client
        ).search(SearchQuery(text="river", limit=1))


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

    # ``application/zip`` is container evidence, not a payload format.  Without
    # an explicit provider format the discovery result must fail closed.
    assert results == ()

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
    assert PyogrioAdapter().supports(resource)


def test_search_ckan_jp_rejects_unsuccessful_response() -> None:
    endpoint = "https://search.ckan.jp/backend/api"
    client = RecordingJsonClient(
        {endpoint + "/package_search": {"success": False, "result": {}}}
    )
    adapter = SearchCkanJpAdapter(endpoint=endpoint, get_json=client)

    with pytest.raises(ProviderResponseError, match="not successful"):
        adapter.search(SearchQuery(text="archive"))


def test_search_ckan_jp_rejects_resource_urls_with_embedded_credentials() -> None:
    adapter = SearchCkanJpAdapter(get_json=lambda url, params: {})

    with pytest.raises(ProviderResponseError, match="embedded credentials"):
        adapter._package_results(  # pyright: ignore[reportPrivateUsage]
            {
                "title": "Private URL",
                "resources": {
                    "id": "secret-1",
                    "url": "https://user:password@example.jp/data.csv",
                    "format": "CSV",
                },
            },
            "https://search.ckan.jp/backend/api",
            {},
        )


@pytest.mark.parametrize("text", ["", " \t\n　"])
def test_search_ckan_jp_blank_text_does_not_search_everything(text: str) -> None:
    adapter = SearchCkanJpAdapter(
        get_json=lambda url, params: pytest.fail("no request")
    )
    assert adapter.search(SearchQuery(text=text)) == ()


def test_search_ckan_jp_literal_and_query_and_actual_provenance() -> None:
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(dict(params))
        return dict(fixture_json("search_ckan_jp/package_search.json"))

    results = SearchCkanJpAdapter(get_json=get_json).search(
        SearchQuery(text="河川　神奈川県 河川", limit=200)
    )
    assert calls == [
        {
            "q": '(xckan_title:"河川"^8 OR xckan_title:*河川*^4 OR "河川") AND '
            '(xckan_title:"神奈川県"^8 OR xckan_title:*神奈川県*^4 OR "神奈川県")',
            "rows": 100,
        }
    ]
    assert results[0].provenance.query_parameters == calls[0]


@pytest.mark.parametrize("term", ["title:*", '"', "\\", "+-&|!(){}[]^~?:/"])
def test_search_ckan_jp_escapes_user_syntax(term: str) -> None:
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(dict(params))
        return {"success": True, "result": {"results": []}}

    assert SearchCkanJpAdapter(get_json=get_json).search(SearchQuery(text=term)) == ()
    escaped = (
        "".join("\\" + char for char in term) if term != "title:*" else "title\\:\\*"
    )
    assert calls[0]["q"] == (
        f'(xckan_title:"{escaped}"^8 OR xckan_title:*{escaped}*^4 OR "{escaped}")'
    )
    assert "rows" not in calls[0]


def test_search_ckan_jp_round_robin_filter_and_cross_site_resource_identity() -> None:
    packages: list[dict[str, Any]] = [
        {
            "xckan_id": "site-a:dataset",
            "xckan_original_id": "dataset",
            "xckan_site_url": "https://a.example/dataset",
            "xckan_title": "河川",
            "title": "old title",
            "resources": [
                {"id": "csv", "url": "https://a.example/1.csv", "format": "CSV"},
                {
                    "id": "shared",
                    "url": "https://a.example/1.json",
                    "format": "GeoJSON",
                },
                {
                    "id": "second",
                    "url": "https://a.example/2.json",
                    "format": "GeoJSON",
                },
            ],
        },
        {
            "xckan_id": "site-b:dataset",
            "xckan_original_id": "dataset",
            "xckan_site_url": "https://b.example/dataset",
            "xckan_title": "河川水質",
            "resources": [
                {
                    "id": "shared",
                    "url": "https://b.example/1.json",
                    "format": "GeoJSON",
                },
            ],
        },
    ]
    response = {
        "success": True,
        "result": {"count": 3, "results": packages + [packages[0]]},
    }
    adapter = SearchCkanJpAdapter(get_json=lambda url, params: response)
    results = adapter.search(
        SearchQuery(text="河川", format=(Format.GEOJSON,), limit=10)
    )
    assert [(r.title, r.provenance.resource_identifier) for r in results] == [
        ("河川", "shared"),
        ("河川水質", "shared"),
        ("河川", "second"),
    ]
    # The old flattened expansion fills limit=2 with site A; both sites now appear.
    limited = adapter.search(
        SearchQuery(text="河川", format=(Format.GEOJSON,), limit=2)
    )
    assert [r.provenance.original_url for r in limited] == [
        "https://a.example/dataset",
        "https://b.example/dataset",
    ]
    resource = Resolver().resolve(DirectAdapter().load(results[0].target))
    assert resource.uri == "https://a.example/1.json"
    assert results[0].metadata.raw["title"] == "old title"


def test_search_ckan_jp_deduplicates_across_pages_and_keeps_page_provenance() -> None:
    package: dict[str, Any] = {
        "id": "global-id",
        "title": "河川",
        "resources": [
            {"id": "one", "url": "https://a.example/1.csv", "format": "CSV"},
        ],
    }
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(dict(params))
        page = (
            package
            if not params.get("start")
            else {
                **package,
                "resources": package["resources"]
                + [
                    {"id": "two", "url": "https://a.example/2.csv", "format": "CSV"},
                ],
            }
        )
        return {"success": True, "result": {"count": 2, "results": [page]}}

    results = SearchCkanJpAdapter(get_json=get_json).search(
        SearchQuery(text="河川", limit=3)
    )
    assert [r.provenance.resource_identifier for r in results] == ["one", "two"]
    assert results[1].provenance.query_parameters == calls[1]
    assert calls[1]["start"] == 1


@pytest.mark.parametrize(
    ("name", "terms"),
    [
        ("東京都府中市", ("東京都", "府中市")),
        ("広島県府中市", ("広島県", "府中市")),
        ("兵庫県美方郡香美町", ("香美町",)),
        ("神奈川県横浜市", ("横浜市",)),
    ],
)
def test_search_ckan_jp_snapshot_area_names_preserve_identity(
    name: str, terms: tuple[str, ...]
) -> None:
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        calls.append(dict(params))
        return {"success": True, "result": {"results": []}}

    assert SearchCkanJpAdapter(get_json=get_json).search(SearchQuery(text=name)) == ()
    assert calls[0]["q"] == " AND ".join(
        f'(xckan_title:"{term}"^8 OR xckan_title:*{term}*^4 OR "{term}")'
        for term in terms
    )


def test_search_ckan_jp_observed_yokohama_resource_names_improve_first_result() -> None:
    excerpt = fixture_json("search_ckan_jp/yokohama_resource_excerpt.json")
    package = excerpt["package"]
    response = {"success": True, "result": {"count": 1, "results": [package]}}
    results = SearchCkanJpAdapter(get_json=lambda url, params: response).search(
        SearchQuery(text="避難所 神奈川県横浜市", limit=1)
    )
    # Real metadata excerpt; the old Resource order starts with population data.
    assert package["resources"][0]["name"].startswith("1-1")
    assert (
        results[0].provenance.resource_identifier
        == "3348ebc3-e9d9-41a7-b652-0b6c7c2c1d1c"
    )
    assert "指定避難所" in results[0].raw_metadata["resource"]["name"]
    assert tuple(results[0].raw_metadata["catalog"]["resources"]) == tuple(
        package["resources"]
    )
    assert results[0].metadata.raw["xckan_site_url"] == package["xckan_site_url"]


def test_search_ckan_jp_resource_names_precede_descriptions_and_area_mentions() -> None:
    resources = [
        {
            "id": "area",
            "name": "横浜市",
            "url": "https://example.org/area.csv",
            "format": "CSV",
        },
        {
            "id": "description",
            "description": "避難所",
            "url": "https://example.org/description.csv",
            "format": "CSV",
        },
        {
            "id": "name",
            "name": "避難所",
            "url": "https://example.org/name.csv",
            "format": "CSV",
        },
        {
            "id": "tied",
            "name": "避難所",
            "url": "https://example.org/tied.csv",
            "format": "CSV",
        },
    ]
    response = {
        "success": True,
        "result": {"results": [{"id": "dataset", "resources": resources}]},
    }
    results = SearchCkanJpAdapter(get_json=lambda url, params: response).search(
        SearchQuery(text="避難所 神奈川県横浜市")
    )
    assert [r.provenance.resource_identifier for r in results] == [
        "name",
        "tied",
        "description",
        "area",
    ]


def test_search_ckan_jp_queries_match_observed_service_requests() -> None:
    observations = fixture_json("search_ckan_jp/search_observations.json")
    for case in observations["cases"].values():
        calls: list[dict[str, Any]] = []

        def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
            calls.append(dict(params))
            return {"success": True, "result": {"count": 0, "results": []}}

        assert (
            SearchCkanJpAdapter(get_json=get_json).search(
                SearchQuery(text=case["text"], limit=10)
            )
            == ()
        )
        assert calls == [case["after"]["request"]]
    river = observations["cases"]["river"]
    assert river["after"]["top_datasets"][0]["xckan_title"] == "河川"
    assert all(p["xckan_title"] != "河川" for p in river["before"]["top_datasets"])
