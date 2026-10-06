from collections.abc import Mapping
from typing import Any

import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import Format, configure
from rhinestone.adapters.source import CkanAdapter, GeospatialJpAdapter
from rhinestone.catalogs import BUILTIN, Catalog
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import SearchQuery
from tests.provider_support import fixture_json


def package(identifier: str, area: object = None, tags: object = ()) -> dict[str, Any]:
    return {
        "id": identifier,
        "title": identifier,
        "area": area,
        "tags": tags,
        "resources": [{"id": identifier, "format": "CSV"}],
    }


class Client:
    def __init__(self, packages: list[dict[str, Any]], page_size: int = 100) -> None:
        self.packages = packages
        self.page_size = page_size
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        assert url.endswith("package_search")
        self.calls.append(dict(params))
        selected = self.packages
        if "fq" in params:
            area = str(params["fq"])[6:-1]
            selected = [
                item for item in selected if {"name": area} in (item.get("tags") or ())
            ]
        start = params.get("start", 0)
        return {
            "success": True,
            "result": {
                "count": len(selected),
                "results": selected[start : start + self.page_size],
            },
        }


def adapter(client: Client) -> GeospatialJpAdapter:
    return GeospatialJpAdapter(client, endpoint="https://catalog.example")


def ids(results: tuple[Any, ...]) -> list[str]:
    return [item.target.settings["resource_id"] for item in results]


def test_synthetic_quality_fixture_improves_area_order_and_dataset_diversity() -> None:
    packages = fixture_json("geospatial_jp/search.json")["result"]["results"]
    original = CkanAdapter(Client(packages), endpoint="https://catalog.example").search(
        SearchQuery(text="河川 神奈川県", limit=5)
    )
    client = Client(packages)
    results = adapter(client).search(SearchQuery(text="河川", area="神奈川県", limit=5))

    assert ids(original) == [
        "incidental-0",
        "incidental-1",
        "national-0",
        "national-1",
        "regional-0",
    ]
    assert ids(results) == [
        "local-0",
        "municipal-0",
        "regional-0",
        "national-0",
        "incidental-0",
    ]
    assert client.calls == [
        {"q": '"河川"', "fq": 'tags:"神奈川県"', "rows": 100, "start": 0},
        {"q": '"河川"', "rows": 100, "start": 0},
    ]
    assert results[0].raw_metadata["package"]["area"] == "神奈川県"
    assert results[0].provenance.query_parameters == client.calls[0]
    assert results[0].provenance.dataset_identifier == "local"
    assert results[0].provenance.adapter == "geospatial-jp"
    assert results[0].target.source_id == "geospatial-jp"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, "*:*"),
        ("  ", "*:*"),
        ("河川 河川　洪水", '"河川" AND "洪水"'),
        ('a"b c\\d', '"a\\"b" AND "c\\\\d"'),
        ("OR *:*", '"OR" AND "*:*"'),
    ],
)
def test_text_is_literal_explicit_and_without_operator_injection(
    text: str | None, expected: str
) -> None:
    client = Client([])
    assert adapter(client).search(SearchQuery(text=text)) == ()
    assert client.calls[0]["q"] == expected


def test_zero_limit_and_unsupported_conditions() -> None:
    client = Client([])
    assert adapter(client).search(SearchQuery(limit=0)) == ()
    assert client.calls == []
    with pytest.raises(ConfigValidationError, match="bbox"):
        adapter(client).search(SearchQuery(bbox=(0, 0, 1, 1)))


def test_tag_match_prioritizes_topic_and_round_robins_resources() -> None:
    first = package("first", tags=[])
    second = package("second", tags=[{"name": "河川"}])
    second["resources"].append({"id": "second-extra", "format": "CSV"})
    assert ids(adapter(Client([first, second])).search(SearchQuery(text="河川"))) == [
        "second",
        "first",
        "second-extra",
    ]


@pytest.mark.parametrize(
    ("area", "matching"),
    [
        ("神奈川県横浜市", "神奈川県_横浜市"),
        ("神奈川県横浜市", "神奈川県"),
        ("神奈川県", "神奈川県_川崎市"),
        ("神奈川県", "関東地方"),
        ("京都府京都市", "関西"),
        ("北海道", "北海道"),
        ("東京都", "全国"),
        ("東京都", "日本全国"),
        ("任意地域", "日本全国"),
    ],
)
def test_explicit_region_metadata_retains_containing_and_contained_candidates(
    area: str, matching: str
) -> None:
    results = adapter(
        Client([package("fallback", "埼玉県"), package("match", matching)])
    ).search(SearchQuery(area=area))
    assert ids(results) == ["match", "fallback"]


def test_missing_metadata_and_unrelated_municipality_are_not_excluded() -> None:
    rows = [
        package("other", "神奈川県_川崎市", None),
        package("unknown", tags=[None, {}, {"name": 5}]),
    ]
    assert ids(adapter(Client(rows)).search(SearchQuery(area="神奈川県横浜市"))) == [
        "other",
        "unknown",
    ]


def test_format_filter_pages_past_empty_and_duplicate_datasets_and_resources() -> None:
    skipped = package("skip")
    skipped["resources"].append(
        {"id": "undeclared", "url": "https://example.test/fake.geojson"}
    )
    matching = package("match", "神奈川県", [{"name": "神奈川県"}])
    matching["resources"] = [
        {"id": "vector", "format": "GeoJSON"},
        {"id": "vector", "format": "GeoJSON"},
        {"id": "extra", "format": "GeoJSON"},
    ]
    client = Client([skipped, matching, matching], page_size=1)
    results = adapter(client).search(
        SearchQuery(area="神奈川県", format=(Format.GEOJSON,), limit=5)
    )
    assert ids(results) == ["vector", "extra"]
    assert all(result.formats == frozenset({"geojson"}) for result in results)
    assert len(client.calls) == 5


def test_finite_limit_keeps_paging_and_none_limit_reads_one_window() -> None:
    client = Client([package("a"), package("b")], page_size=1)
    assert ids(adapter(client).search(SearchQuery(limit=2))) == ["a", "b"]
    assert [call["start"] for call in client.calls] == [0, 1]
    client.calls.clear()
    assert ids(adapter(client).search(SearchQuery())) == ["a"]
    assert len(client.calls) == 1


@pytest.mark.parametrize("count", [None, True, -1, "1"])
def test_invalid_count_is_a_response_error(count: object) -> None:
    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"success": True, "result": {"count": count, "results": []}}

    with pytest.raises(ProviderResponseError, match="count"):
        GeospatialJpAdapter(get_json, endpoint="https://example.test").search(
            SearchQuery()
        )


def test_empty_page_before_count_is_a_response_error() -> None:
    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"success": True, "result": {"count": 1, "results": []}}

    with pytest.raises(ProviderResponseError, match="empty"):
        GeospatialJpAdapter(get_json, endpoint="https://example.test").search(
            SearchQuery()
        )


def test_public_area_search_resolves_alias_keeps_text_and_resolves_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packages = fixture_json("geospatial_jp/search.json")["result"]["results"]
    client = Client(packages)

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        if url.endswith("package_search"):
            return client(url, params)
        if url.endswith("resource_show"):
            return {"success": True, "result": packages[3]["resources"][0]}
        assert url.endswith("package_show")
        return {"success": True, "result": packages[3]}

    monkeypatch.setattr(_http, "get_json", get_json)
    app = configure(catalog=Catalog((BUILTIN[0],)))
    results = app.search(
        text="河川", area="Kanagawa", format=(Format.GEOJSON,), limit=3
    )
    assert results.diagnostics == ()
    assert ids(results["geospatial-jp"]) == ["local-0", "municipal-0", "regional-0"]
    resource = app.resolve(results["geospatial-jp"][0])
    assert resource.uri == "https://files.example/local-0"
    assert resource.format == "geojson"
    assert resource.provenance.provider == "geospatial-jp"
    assert resource.provenance.adapter == "geospatial-jp"
    assert resource.provenance.raw["package"]["area"] == "神奈川県"


@pytest.mark.parametrize(
    ("requested", "declared"),
    [
        ("北海道虻田郡ニセコ町", "北海道_ニセコ町"),
        ("ニセコ町", "北海道_ニセコ町"),
        ("福島県郡山市", "福島県_郡山市"),
    ],
)
def test_public_municipality_search_matches_provider_names_before_prefecture(
    monkeypatch: pytest.MonkeyPatch, requested: str, declared: str
) -> None:
    prefecture, municipality = declared.split("_")
    client = Client([package("broad", prefecture), package("exact", declared)])
    monkeypatch.setattr(_http, "get_json", client)
    results = configure(catalog=Catalog((BUILTIN[0],))).search(
        text="避難所", area=requested, limit=1
    )
    assert results.diagnostics == ()
    assert ids(results["geospatial-jp"]) == ["exact"]
    assert client.calls[0]["fq"] == f'tags:"{prefecture}{municipality}"'
