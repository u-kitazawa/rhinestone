from datetime import datetime, timezone
from typing import Any, cast

import pytest

from rhinestone._composition import (  # pyright: ignore[reportPrivateUsage]
    ConfiguredSourceAdapter,
)
from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.adapters.source.stac.adapter import (
    _comparable_interval,  # pyright: ignore[reportPrivateUsage]
    _stac_datetime,  # pyright: ignore[reportPrivateUsage]
)
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Reference, SearchQuery
from tests.provider_support import (
    RecordingJsonClient,
    ResponseJsonClient,
    fixture_json,
)


@pytest.mark.parametrize("invalid_item", [None, False, 1, "fixture-secret", [], [{}]])
def test_public_stac_search_isolates_non_object_items(
    monkeypatch: pytest.MonkeyPatch, invalid_item: object
) -> None:
    import rhinestone._http as http  # pyright: ignore[reportPrivateUsage]
    from rhinestone import Catalog, Provider, configure

    first = fixture_json("stac/item_collection.json")["features"][0]
    second = {**first, "id": "scene-2"}

    def get_json(*args: Any, **kwargs: Any) -> dict[str, object]:
        return {"features": [first, invalid_item, second]}

    monkeypatch.setattr(http, "get_json", get_json)
    app = configure(
        catalog=Catalog(
            (Provider("imagery", "stac", {"endpoint": "https://stac.example"}),)
        )
    )

    results = app.search()

    assert [r.reference.resource_identifier for r in results] == [
        "scene-1:visual",
        "scene-2:visual",
    ]
    assert results[0].metadata.title == "Tokyo scene"
    assert results[0].metadata.raw["bbox"] == tuple(first["bbox"])
    assert results[0].provenance.resource_identifier == "scene-1:visual"
    assert len(results.diagnostics) == 1
    diagnostic = results.diagnostics[0]
    assert diagnostic.source_id == "imagery"
    assert diagnostic.reason == "item_skipped"
    assert diagnostic.detail == "invalid_item"
    assert diagnostic.resource_identifier is None
    assert "fixture-secret" not in repr(results.diagnostics)


@pytest.mark.parametrize(
    "features", [None, "invalid", 1, False, {}, {"id": "scene-1", "assets": {}}]
)
def test_stac_api_rejects_invalid_feature_container(features: object) -> None:
    adapter = StacAdapter(
        endpoint="https://stac.example",
        get_json=RecordingJsonClient(
            {"https://stac.example/search": {"features": features}}
        ),
    )
    with pytest.raises(ProviderResponseError, match="STAC features"):
        adapter.search(SearchQuery())


def test_stac_load_selects_only_the_explicit_asset_and_preserves_item() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})
    adapter = StacAdapter(get_json=client)
    source = adapter.load(
        Reference(
            "stac",
            parameters={
                "endpoint": endpoint,
                "collection_id": "sentinel-2",
                "item_id": "scene-1",
                "asset_key": "visual",
            },
        )
    )
    assert client.calls == [(item_url, {})]
    assert source.uri == "https://assets.example/scene-1.tif"
    assert source.media_type is not None
    assert source.media_type.startswith("image/tiff")
    assert source.format == "cog"
    assert source.reference.parameters["asset_key"] == "visual"
    assert source.metadata.title == "Tokyo scene"
    assert source.provenance.dataset_identifier == "sentinel-2"
    assert source.provenance.resource_identifier == "scene-1:visual"
    assert source.metadata.raw["assets"]["thumbnail"]["roles"] == ("thumbnail",)


@pytest.mark.parametrize(
    ("media_type", "expected_format"),
    [
        ("image/tiff; application=geotiff; profile=cloud-optimized", "cog"),
        ("image/tiff", "geotiff"),
        ("application/geo+json", "geojson"),
        ("text/csv", "csv"),
        ("application/json", "json"),
        ("application/x-unknown", None),
        (None, None),
    ],
)
def test_stac_search_and_load_match_documented_media_type_contract(
    media_type: str | None, expected_format: str | None
) -> None:
    """対応表が形式判定と実行可否を混同せず、URLから形式を推測しないための回帰。"""
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    asset: dict[str, object] = {
        "href": "https://assets.example/data.tif",
        "roles": ["data"],
    }
    if media_type is not None:
        asset["type"] = media_type
    item = dict(fixture_json("stac/item.json"))
    item["assets"] = {"data": asset}
    client = RecordingJsonClient(
        {endpoint + "/search": {"features": [item]}, item_url: item}
    )
    adapter = StacAdapter(endpoint=endpoint, get_json=client)

    results = adapter.search(SearchQuery())
    assert len(results) == 1
    loaded = adapter.load(results[0].reference)
    for resource in (results[0], loaded):
        assert resource.uri == asset["href"]
        assert resource.media_type == media_type
        assert resource.format == expected_format
        if expected_format is None:
            assert resource.access_plan is None
        else:
            assert resource.access_plan is not None
            assert resource.access_plan.format == expected_format
    assert client.calls == [(endpoint + "/search", {}), (item_url, {})]


@pytest.mark.parametrize("provider_count", [0, 1, 2])
def test_stac_api_zero_limit_returns_no_resources_without_requests(
    monkeypatch: pytest.MonkeyPatch, provider_count: int
) -> None:
    import rhinestone._http as http  # pyright: ignore[reportPrivateUsage]
    from rhinestone import Catalog, Provider, configure

    endpoint = "https://stac.example"
    client = RecordingJsonClient(
        {endpoint + "/search": fixture_json("stac/item_collection.json")}
    )
    if provider_count == 0:
        results = StacAdapter(endpoint=endpoint, get_json=client).search(
            SearchQuery(limit=0)
        )
    else:
        monkeypatch.setattr(http, "get_json", client)
        app = configure(
            catalog=Catalog(
                tuple(
                    Provider(f"stac-{index}", "stac", {"endpoint": endpoint})
                    for index in range(provider_count)
                )
            )
        )
        results = app.search(limit=0)
    assert len(results) == 0
    assert client.calls == []


def test_stac_search_maps_spatial_temporal_and_collection_conditions() -> None:
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"
    client = RecordingJsonClient(
        {search_url: fixture_json("stac/item_collection.json")}
    )
    adapter = StacAdapter(endpoint=endpoint, get_json=client)
    results = adapter.search(
        SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0), limit=2),
        collections=("sentinel-2",),
    )
    assert client.calls == [
        (
            search_url,
            {
                "bbox": "139.0,35.0,140.0,36.0",
                "collections": "sentinel-2",
                "limit": 2,
            },
        )
    ]
    assert results[0].reference == Reference(
        "stac",
        "sentinel-2",
        "scene-1:visual",
        {
            "collection_id": "sentinel-2",
            "item_id": "scene-1",
            "asset_key": "visual",
        },
    )
    assert "endpoint" not in results[0].reference.parameters
    assert results[0].metadata.raw["stac_version"] == "1.0.0"


def test_stac_search_returns_each_data_asset_and_skips_missing_data() -> None:
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"

    def item(item_id: str, assets: dict[str, object]) -> dict[str, object]:
        return {
            "id": item_id,
            "collection": "imagery",
            "properties": {"title": item_id},
            "assets": assets,
        }

    response: dict[str, object] = {
        "features": [
            item("missing", {"thumbnail": {"href": "https://thumb"}}),
            item(
                "usable",
                {
                    "visual": {
                        "href": "https://assets.example/usable.tif",
                        "type": "image/tiff; application=geotiff",
                        "roles": ["data"],
                    }
                },
            ),
            item(
                "ambiguous",
                {
                    "red": {"href": "https://red", "roles": ["data"]},
                    "green": {"href": "https://green", "roles": ["data"]},
                },
            ),
        ]
    }
    results = StacAdapter(
        endpoint=endpoint, get_json=RecordingJsonClient({search_url: response})
    ).search(SearchQuery())

    assert [result.title for result in results] == [
        "usable",
        "ambiguous",
        "ambiguous",
    ]
    assert results[0].reference.parameters["asset_key"] == "visual"
    assert [result.reference.parameters["asset_key"] for result in results[1:]] == [
        "green",
        "red",
    ]
    assert [result.uri for result in results[1:]] == ["https://green", "https://red"]
    assert [diagnostic.resource_identifier for diagnostic in results.diagnostics] == [
        "missing",
    ]
    assert [diagnostic.detail for diagnostic in results.diagnostics] == [
        "missing_data_asset",
    ]


def test_stac_search_isolates_invalid_items() -> None:
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"

    def item(item_id: str, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "id": item_id,
            "collection": "imagery",
            "properties": {"title": item_id},
            "assets": {
                "visual": {
                    "href": f"https://assets.example/{item_id}.tif",
                    "roles": ["data"],
                }
            },
        }
        value.update(overrides)
        return value

    response: dict[str, object] = {
        "features": [
            {"collection": "imagery", "properties": {}, "assets": {}},
            item("   "),
            item("bad-collection", collection="   "),
            item("bad-properties", properties=None),
            item("bad-assets", assets=None),
            item(
                "bad-href",
                assets={"visual": {"href": None, "roles": ["data"]}},
            ),
            item(
                "malformed-href",
                assets={"visual": {"href": "https://[invalid", "roles": ["data"]}},
            ),
            item("usable"),
        ]
    }

    results = StacAdapter(
        endpoint=endpoint, get_json=RecordingJsonClient({search_url: response})
    ).search(SearchQuery())

    assert [result.title for result in results] == ["usable"]
    assert [diagnostic.reason for diagnostic in results.diagnostics] == [
        "item_skipped",
        "item_skipped",
        "item_skipped",
        "item_skipped",
        "item_skipped",
        "item_skipped",
        "item_skipped",
    ]
    assert [diagnostic.resource_identifier for diagnostic in results.diagnostics] == [
        None,
        None,
        "bad-collection",
        "bad-properties",
        "bad-assets",
        "bad-href",
        "malformed-href",
    ]
    assert [diagnostic.detail for diagnostic in results.diagnostics] == [
        "invalid_item",
        "invalid_item",
        "invalid_item",
        "invalid_item",
        "invalid_item",
        "invalid_item",
        "invalid_item",
    ]


def test_static_stac_search_traverses_links_and_returns_reloadable_resource() -> None:
    catalog_uri = "https://static.example/catalog.json"
    collection_uri = "https://static.example/collections/elevation/collection.json"
    item_uri = "https://static.example/collections/elevation/items/tokyo.json"
    root = {
        "type": "Catalog",
        "links": [
            {"rel": "self", "href": catalog_uri},
            {"rel": "child", "href": "./collections/elevation/collection.json"},
        ],
    }
    collection = {
        "type": "Collection",
        "id": "elevation",
        "links": [
            {"rel": "root", "href": "../../catalog.json"},
            {"rel": "item", "href": "./items/tokyo.json"},
        ],
    }
    item = {
        "type": "Feature",
        "id": "tokyo-dem",
        "collection": "elevation",
        "bbox": [139.0, 35.0, 140.0, 36.0],
        "properties": {
            "title": "Tokyo DEM",
            "datetime": "2026-01-02T03:04:05Z",
        },
        "assets": {
            "dem": {
                "href": "../assets/tokyo.tif",
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data"],
            }
        },
        "links": [{"rel": "parent", "href": "../collection.json"}],
    }
    client = RecordingJsonClient(
        {catalog_uri: root, collection_uri: collection, item_uri: item}
    )
    adapter = StacAdapter(get_json=client, catalog_uri=catalog_uri)

    results = adapter.search(
        SearchQuery(
            bbox=(139.5, 35.5, 140.5, 36.5),
            time=(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 3, tzinfo=timezone.utc),
            ),
            limit=1,
        )
    )

    assert [result.title for result in results] == ["Tokyo DEM"]
    assert results[0].uri == (
        "https://static.example/collections/elevation/assets/tokyo.tif"
    )
    assert results[0].format == "cog"
    assert results[0].reference.parameters["item_href"] == item_uri
    assert client.calls == [
        (catalog_uri, {}),
        (collection_uri, {}),
        (item_uri, {}),
    ]

    reloaded = adapter.load(results[0].reference)

    assert reloaded.uri == results[0].uri
    assert client.calls[-1] == (item_uri, {})
    assert len(adapter.search(SearchQuery())) == 1


def test_static_stac_search_is_bounded_and_cycle_safe() -> None:
    catalog_uri = "https://static.example/catalog.json"
    child_uri = "https://static.example/child.json"
    client = RecordingJsonClient(
        {
            catalog_uri: {
                "type": "Catalog",
                "links": [{"rel": "child", "href": child_uri}],
            },
            child_uri: {
                "type": "Catalog",
                "links": [
                    {"rel": "child", "href": catalog_uri},
                    {"rel": "child", "href": "https://static.example/third.json"},
                ],
            },
        }
    )
    adapter = StacAdapter(get_json=client, catalog_uri=catalog_uri, max_documents=2)

    with pytest.raises(ProviderResponseError, match="max_documents"):
        adapter.search(SearchQuery())

    assert client.calls == [(catalog_uri, {}), (child_uri, {})]


def test_static_stac_configuration_is_explicit() -> None:
    with pytest.raises(ConfigValidationError, match="either endpoint or catalog_uri"):
        StacAdapter(
            get_json=RecordingJsonClient({}),
            endpoint="https://api.example",
            catalog_uri="https://static.example/catalog.json",
        )

    with pytest.raises(ConfigValidationError, match="positive integer"):
        StacAdapter(
            get_json=RecordingJsonClient({}),
            catalog_uri="https://static.example/catalog.json",
            max_documents=0,
        )

    with pytest.raises(ConfigValidationError, match="positive integer"):
        StacAdapter(
            get_json=RecordingJsonClient({}),
            catalog_uri="https://static.example/catalog.json",
            max_documents=cast(Any, True),
        )


@pytest.mark.parametrize(
    "catalog_uri",
    (cast(Any, 1), "", "https://[invalid", "https://user:pass@example.com/catalog"),
)
def test_static_stac_rejects_invalid_catalog_uri(catalog_uri: str) -> None:
    with pytest.raises(ConfigValidationError, match="catalog_uri must be a valid URI"):
        StacAdapter(
            get_json=RecordingJsonClient({}),
            catalog_uri=catalog_uri,
        )


def test_static_stac_zero_limit_avoids_catalog_request() -> None:
    client = RecordingJsonClient({})
    adapter = StacAdapter(
        get_json=client, catalog_uri="https://static.example/catalog.json"
    )

    assert not adapter.search(SearchQuery(limit=0))
    assert client.calls == []


def test_static_stac_rejects_unsupported_search_condition() -> None:
    adapter = StacAdapter(
        get_json=RecordingJsonClient({}),
        catalog_uri="https://static.example/catalog.json",
    )

    with pytest.raises(ConfigValidationError, match="text"):
        adapter.search(SearchQuery(text="elevation"))


def test_api_stac_rejects_static_item_href() -> None:
    adapter = StacAdapter(
        get_json=RecordingJsonClient({}), endpoint="https://api.example"
    )

    with pytest.raises(ConfigValidationError, match="static STAC Provider"):
        adapter.load(
            Reference(
                "stac",
                parameters={
                    "collection_id": "elevation",
                    "item_id": "tokyo",
                    "asset_key": "dem",
                    "item_href": "https://static.example/tokyo.json",
                },
            )
        )


def test_static_stac_rejects_malformed_item_href() -> None:
    adapter = StacAdapter(
        get_json=RecordingJsonClient({}),
        catalog_uri="https://static.example/catalog.json",
    )

    with pytest.raises(ConfigValidationError, match="item_href is invalid"):
        adapter.load(
            Reference(
                "stac",
                parameters={
                    "collection_id": "elevation",
                    "item_id": "tokyo",
                    "asset_key": "dem",
                    "item_href": "https://[invalid",
                },
            )
        )


def test_static_stac_reports_invalid_and_missing_data_items() -> None:
    catalog_uri = "https://static.example/catalog.json"
    invalid_uri = "https://static.example/invalid.json"
    missing_uri = "https://static.example/missing.json"
    client = RecordingJsonClient(
        {
            catalog_uri: {
                "type": "Catalog",
                "links": [
                    {"rel": "item", "href": invalid_uri},
                    {"rel": "item", "href": missing_uri},
                ],
            },
            invalid_uri: {
                "type": "Feature",
                "collection": "elevation",
                "properties": {},
                "assets": {},
            },
            missing_uri: {
                "type": "Feature",
                "id": "missing",
                "collection": "elevation",
                "properties": {},
                "assets": {},
            },
        }
    )

    results = StacAdapter(get_json=client, catalog_uri=catalog_uri).search(
        SearchQuery()
    )

    assert not results
    assert [item.detail for item in results.diagnostics] == [
        "invalid_item",
        "missing_data_asset",
    ]


def test_static_stac_skips_duplicate_and_non_traversal_links() -> None:
    catalog_uri = "https://static.example/catalog.json"
    child_uri = "https://static.example/child.json"
    client = RecordingJsonClient(
        {
            catalog_uri: {
                "type": "Catalog",
                "links": [
                    {"rel": "self", "href": catalog_uri},
                    {"rel": "child", "href": child_uri},
                    {"rel": "child", "href": child_uri},
                ],
            },
            child_uri: {"type": "Catalog", "links": []},
        }
    )

    results = StacAdapter(
        get_json=client,
        catalog_uri=catalog_uri,
        max_documents=2,
    ).search(SearchQuery())

    assert not results
    assert client.calls == [(catalog_uri, {}), (child_uri, {})]


def test_static_stac_preserves_catalog_trailing_slash_for_relative_links() -> None:
    catalog_uri = "https://static.example/catalog/"
    item_uri = "https://static.example/catalog/item.json"
    client = RecordingJsonClient(
        {
            catalog_uri: {
                "type": "Catalog",
                "links": [{"rel": "item", "href": "item.json"}],
            },
            item_uri: {
                "type": "Feature",
                "id": "item",
                "collection": "elevation",
                "properties": {},
                "assets": {},
            },
        }
    )

    StacAdapter(get_json=client, catalog_uri=catalog_uri).search(SearchQuery())

    assert client.calls == [(catalog_uri, {}), (item_uri, {})]


def test_static_stac_rejects_malformed_link_href() -> None:
    catalog_uri = "https://static.example/catalog.json"
    adapter = StacAdapter(
        get_json=RecordingJsonClient(
            {
                catalog_uri: {
                    "type": "Catalog",
                    "links": [{"rel": "child", "href": "https://[invalid"}],
                }
            }
        ),
        catalog_uri=catalog_uri,
    )

    with pytest.raises(ProviderResponseError, match="link href"):
        adapter.search(SearchQuery())


@pytest.mark.parametrize(
    "item_bbox",
    (
        [137.0, 35.0, 138.0, 36.0],
        [141.0, 35.0, 142.0, 36.0],
        [139.0, 33.0, 140.0, 34.0],
        [139.0, 37.0, 140.0, 38.0],
        None,
        [139.0, 35.0, 140.0],
        [139.0, 35.0, 0.0, 140.0, 36.0, 100.0],
        ["invalid", 35.0, 140.0, 36.0],
        ["139.0", 35.0, 140.0, 36.0],
        [True, 35.0, 140.0, 36.0],
        [float("inf"), 35.0, 140.0, 36.0],
        [float("nan"), 35.0, 140.0, 36.0],
    ),
)
def test_static_stac_filters_nonmatching_or_invalid_bboxes(
    item_bbox: object,
) -> None:
    catalog_uri = "https://static.example/catalog.json"
    item_uri = "https://static.example/item.json"
    item = {
        "type": "Feature",
        "id": "outside",
        "collection": "elevation",
        "bbox": item_bbox,
        "properties": {},
        "assets": {
            "dem": {
                "href": "./dem.tif",
                "roles": ["data"],
            }
        },
    }
    adapter = StacAdapter(
        get_json=RecordingJsonClient(
            {
                catalog_uri: {
                    "type": "Catalog",
                    "links": [{"rel": "item", "href": item_uri}],
                },
                item_uri: item,
            }
        ),
        catalog_uri=catalog_uri,
    )

    assert not adapter.search(SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0)))


@pytest.mark.parametrize(
    "item_bbox,query_bbox,expected",
    [
        ([170, -40, 175, -30], (160.6, -55.95, -170, -25.89), True),
        ([-175, -40, -172, -30], (160.6, -55.95, -170, -25.89), True),
        ([0, -40, 5, -30], (160.6, -55.95, -170, -25.89), False),
        ([170, 30, 175, 40], (160.6, -55.95, -170, -25.89), False),
        ([170, -40, -170, -30], (172, -39, 175, -31), True),
        ([170, -40, -170, -30], (-175, -39, -172, -31), True),
        ([170, -40, -170, -30], (0, -39, 5, -31), False),
        ([170, -40, -170, -30], (175, -39, -175, -31), True),
        ([170, -40, 175, -30], (175, -40, 179, -30), True),
        ([175, -1, 180, 1], (-180, -1, -175, 1), True),
        ([-180, -1, -175, 1], (175, -1, 180, 1), True),
        ([180, -1, 180, 1], (-180, -1, -180, 1), True),
        ([-180, -1, -180, 1], (180, -1, 180, 1), True),
    ],
)
def test_static_stac_bbox_intersection_preserves_antimeridian_semantics(
    item_bbox: list[float],
    query_bbox: tuple[float, float, float, float],
    expected: bool,
) -> None:
    """Crossing query and Item boxes retain both sides and exclude the middle."""
    catalog_uri = "https://static.example/catalog.json"
    item_uri = "https://static.example/item.json"
    adapter = StacAdapter(
        get_json=RecordingJsonClient(
            {
                catalog_uri: {
                    "type": "Catalog",
                    "links": [{"rel": "item", "href": item_uri}],
                },
                item_uri: {
                    "type": "Feature",
                    "id": "selected",
                    "collection": "sample",
                    "bbox": item_bbox,
                    "properties": {},
                    "assets": {"data": {"href": "./data.tif", "roles": ["data"]}},
                },
            }
        ),
        catalog_uri=catalog_uri,
    )
    results = adapter.search(SearchQuery(bbox=query_bbox))
    assert bool(results) is expected
    if expected:
        assert results[0].uri == "https://static.example/data.tif"


def test_static_stac_filters_collection_and_time() -> None:
    adapter = StacAdapter(
        get_json=RecordingJsonClient({}),
        catalog_uri="https://static.example/catalog.json",
    )
    item = {
        "type": "Feature",
        "id": "tokyo",
        "collection": "elevation",
        "bbox": [139.0, 35.0, 140.0, 36.0],
        "properties": {"datetime": "invalid"},
        "assets": {},
    }

    assert not adapter._matches_static_query(  # pyright: ignore[reportPrivateUsage]
        item, SearchQuery(), ("land-cover",)
    )
    assert not adapter._matches_static_query(  # pyright: ignore[reportPrivateUsage]
        item,
        SearchQuery(time=(datetime(2026, 1, 1), datetime(2026, 1, 2))),
        (),
    )
    item["properties"] = {
        "start_datetime": "2026-01-03T00:00:00Z",
        "end_datetime": "2026-01-04T00:00:00Z",
    }
    assert not adapter._matches_static_query(  # pyright: ignore[reportPrivateUsage]
        item,
        SearchQuery(time=(datetime(2026, 1, 1), datetime(2026, 1, 2))),
        (),
    )
    assert not adapter._matches_static_query(  # pyright: ignore[reportPrivateUsage]
        item,
        SearchQuery(time=(datetime(2026, 1, 5), datetime(2026, 1, 6))),
        (),
    )


@pytest.mark.parametrize(
    ("item_start", "item_end", "query_start", "query_end", "aware"),
    (
        (
            datetime(2026, 1, 1),
            datetime(2026, 1, 2),
            None,
            None,
            False,
        ),
        (
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            None,
            True,
        ),
        (
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            datetime(2026, 1, 1),
            None,
            False,
        ),
        (
            datetime(2026, 1, 1),
            datetime(2026, 1, 2),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            None,
            True,
        ),
        (
            datetime(2026, 1, 1),
            datetime(2026, 1, 2),
            datetime(2026, 1, 1),
            None,
            False,
        ),
    ),
)
def test_static_stac_normalizes_datetime_awareness(
    item_start: datetime,
    item_end: datetime,
    query_start: datetime | None,
    query_end: datetime | None,
    aware: bool,
) -> None:
    start, end = _comparable_interval(item_start, item_end, query_start, query_end)

    assert (start.utcoffset() is not None) is aware
    assert (end.utcoffset() is not None) is aware


def test_invalid_stac_datetime_returns_none() -> None:
    assert _stac_datetime(None) is None
    assert _stac_datetime("") is None
    assert _stac_datetime("not-a-datetime") is None


def test_configured_stac_search_rebinds_item_diagnostic_source() -> None:
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"
    adapter = StacAdapter(
        endpoint=endpoint,
        get_json=RecordingJsonClient(
            {
                search_url: {
                    "features": [
                        {
                            "id": "ambiguous",
                            "collection": "imagery",
                            "properties": {},
                            "assets": {},
                        }
                    ]
                }
            }
        ),
    )

    results = ConfiguredSourceAdapter("earth-observation", adapter, "stac").search(
        SearchQuery()
    )

    assert not isinstance(results, tuple)
    assert results.diagnostics[0].source_id == "earth-observation"


def test_stac_requires_explicit_asset_key() -> None:
    with pytest.raises(ConfigValidationError, match="asset_key"):
        StacAdapter(get_json=RecordingJsonClient({})).load(
            Reference(
                "stac",
                parameters={
                    "endpoint": "https://stac.example",
                    "collection_id": "sentinel-2",
                    "item_id": "scene-1",
                },
            )
        )


def test_stac_missing_requested_asset_is_a_response_error() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})
    with pytest.raises(ProviderResponseError, match="missing"):
        StacAdapter(get_json=client).load(
            Reference(
                "stac",
                parameters={
                    "endpoint": endpoint,
                    "collection_id": "sentinel-2",
                    "item_id": "scene-1",
                    "asset_key": "missing",
                },
            )
        )


def test_stac_resolves_relative_asset_href_against_item_response_uri() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    item = dict(fixture_json("stac/item.json"))
    assets = dict(item["assets"])
    visual = dict(assets["visual"])
    visual["href"] = "./assets/image.tif?download=1#visual"
    assets["visual"] = visual
    item["assets"] = assets
    client = RecordingJsonClient({item_url: item})

    source = StacAdapter(get_json=client).load(
        Reference(
            "stac",
            parameters={
                "endpoint": endpoint,
                "collection_id": "sentinel-2",
                "item_id": "scene-1",
                "asset_key": "visual",
            },
        )
    )

    resolved_uri = (
        "https://stac.example/collections/sentinel-2/items/"
        "assets/image.tif?download=1#visual"
    )
    assert source.uri == resolved_uri
    assert source.provenance.original_url == resolved_uri
    assert source.metadata.raw["assets"]["visual"]["href"] == (
        "./assets/image.tif?download=1#visual"
    )


def test_stac_relative_href_uses_rfc3986_query_and_fragment_rules() -> None:
    adapter = StacAdapter(get_json=RecordingJsonClient({}))
    uri, _, _ = adapter._delivery(  # pyright: ignore[reportPrivateUsage]
        {"href": "./asset.tif", "type": "image/tiff"},
        "https://stac.example/items/scene-1?token=x#old",
    )

    assert uri == "https://stac.example/items/asset.tif"


def test_stac_resolves_relative_href_against_final_redirect_uri() -> None:
    item_url = "https://stac.example/collections/sentinel-2/items/scene-1"
    item = dict(fixture_json("stac/item.json"))
    assets = dict(item["assets"])
    visual = dict(assets["visual"])
    visual["href"] = "./assets/image.tif"
    assets["visual"] = visual
    item["assets"] = assets
    client = ResponseJsonClient(
        {item_url: item},
        {item_url: "https://stac-cdn.example/items/scene-1"},
    )

    source = StacAdapter(get_json=client).load(
        Reference(
            "stac",
            parameters={
                "endpoint": "https://stac.example",
                "collection_id": "sentinel-2",
                "item_id": "scene-1",
                "asset_key": "visual",
            },
        )
    )

    assert source.uri == "https://stac-cdn.example/items/assets/image.tif"


def test_stac_preserves_absolute_non_http_asset_href() -> None:
    adapter = StacAdapter(get_json=RecordingJsonClient({}))
    uri, _, _ = adapter._delivery(  # pyright: ignore[reportPrivateUsage]
        {"href": "s3://bucket/asset.tif", "type": "image/tiff"},
        "https://stac.example/items/scene-1",
    )

    assert uri == "s3://bucket/asset.tif"


def test_stac_load_encodes_identifiers_as_individual_path_segments() -> None:
    endpoint = "https://stac.example"
    collection_id = "sentinel/2?archive#v1"
    item_id = "already%2Fencoded"
    item_url = (
        endpoint + "/collections/sentinel%2F2%3Farchive%23v1/items/already%252Fencoded"
    )
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})

    source = StacAdapter(get_json=client).load(
        Reference(
            "stac",
            parameters={
                "endpoint": endpoint,
                "collection_id": collection_id,
                "item_id": item_id,
                "asset_key": "visual",
            },
        )
    )

    assert client.calls == [(item_url, {})]
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == f"{item_id}:visual"


def test_stac_load_escapes_dot_only_identifier_segments() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/%2E/items/%2E%2E"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})

    source = StacAdapter(get_json=client).load(
        Reference(
            "stac",
            parameters={
                "endpoint": endpoint,
                "collection_id": ".",
                "item_id": "..",
                "asset_key": "visual",
            },
        )
    )

    assert client.calls == [(item_url, {})]
    assert source.provenance.dataset_identifier == "."
    assert source.provenance.resource_identifier == "..:visual"


def test_stac_search_result_keeps_logical_identifiers_for_encoded_load() -> None:
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"
    collection_id = "sentinel/2"
    item_id = "scene?revision#1%"
    item_url = endpoint + "/collections/sentinel%2F2/items/scene%3Frevision%231%25"
    search_response = dict(fixture_json("stac/item_collection.json"))
    feature = dict(search_response["features"][0])
    feature.update({"collection": collection_id, "id": item_id})
    search_response["features"] = [feature]
    client = RecordingJsonClient(
        {
            search_url: search_response,
            item_url: fixture_json("stac/item.json"),
        }
    )
    adapter = StacAdapter(endpoint=endpoint, get_json=client)

    result = adapter.search(SearchQuery(limit=1))[0]
    source = adapter.load(result.reference)

    assert result.reference.parameters["collection_id"] == collection_id
    assert result.reference.parameters["item_id"] == item_id
    assert result.provenance.dataset_identifier == collection_id
    assert result.provenance.resource_identifier == f"{item_id}:visual"
    assert client.calls == [(search_url, {"limit": 1}), (item_url, {})]
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == f"{item_id}:visual"
