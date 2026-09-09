import pytest

from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import (
    RecordingJsonClient,
    ResponseJsonClient,
    fixture_json,
)


def test_stac_load_selects_only_the_explicit_asset_and_preserves_item() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})
    adapter = StacAdapter(get_json=client)
    source = adapter.load(
        Config(
            "stac",
            {
                "endpoint": endpoint,
                "collection_id": "sentinel-2",
                "item_id": "scene-1",
                "asset_key": "visual",
            },
        )
    )
    assert client.calls == [(item_url, {})]
    assert len(source.candidates) == 1
    assert source.candidates[0].uri == "https://assets.example/scene-1.tif"
    assert source.candidates[0].media_type is not None
    assert source.candidates[0].media_type.startswith("image/tiff")
    assert source.candidates[0].attributes["asset_key"] == "visual"
    assert source.metadata.title == "Tokyo scene"
    assert source.provenance.dataset_identifier == "sentinel-2"
    assert source.provenance.resource_identifier == "scene-1"
    assert source.raw_metadata["assets"]["thumbnail"]["roles"] == ("thumbnail",)


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
    assert results[0].to_config() == Config(
        "stac",
        {
            "collection_id": "sentinel-2",
            "item_id": "scene-1",
            "asset_key": "visual",
        },
    )
    assert "endpoint" not in results[0].target.settings
    assert results[0].metadata.raw["stac_version"] == "1.0.0"


def test_stac_requires_explicit_asset_key() -> None:
    with pytest.raises(ConfigValidationError, match="asset_key"):
        StacAdapter(get_json=RecordingJsonClient({})).load(
            Config(
                "stac",
                {
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
            Config(
                "stac",
                {
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
        Config(
            "stac",
            {
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
    assert source.candidates[0].uri == resolved_uri
    assert source.provenance.original_url == resolved_uri
    assert source.raw_metadata["assets"]["visual"]["href"] == (
        "./assets/image.tif?download=1#visual"
    )


def test_stac_relative_href_uses_rfc3986_query_and_fragment_rules() -> None:
    adapter = StacAdapter(get_json=RecordingJsonClient({}))
    candidate = adapter._candidate(  # pyright: ignore[reportPrivateUsage]
        {"href": "./asset.tif", "type": "image/tiff"},
        "visual",
        "https://stac.example/items/scene-1?token=x#old",
    )

    assert candidate.uri == "https://stac.example/items/asset.tif"


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
        Config(
            "stac",
            {
                "endpoint": "https://stac.example",
                "collection_id": "sentinel-2",
                "item_id": "scene-1",
                "asset_key": "visual",
            },
        )
    )

    assert source.candidates[0].uri == "https://stac-cdn.example/items/assets/image.tif"


def test_stac_preserves_absolute_non_http_asset_href() -> None:
    adapter = StacAdapter(get_json=RecordingJsonClient({}))
    candidate = adapter._candidate(  # pyright: ignore[reportPrivateUsage]
        {"href": "s3://bucket/asset.tif", "type": "image/tiff"},
        "visual",
        "https://stac.example/items/scene-1",
    )

    assert candidate.uri == "s3://bucket/asset.tif"
