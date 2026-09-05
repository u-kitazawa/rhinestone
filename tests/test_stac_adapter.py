import pytest

from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import RecordingJsonClient, fixture_json


def test_stac_load_selects_only_the_explicit_asset_and_preserves_item() -> None:
    """複数 asset から用途を推測せず、明示 asset_key の Resource だけを選ぶために必要である。"""
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})
    adapter = StacAdapter(get_json=client)

    source = adapter.load(
        Config(
            source_type="stac",
            settings={
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
    """STAC Item Search の bbox/datetime/collectionsを公式パラメータへ損失なく変換するために必要である。"""
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"
    client = RecordingJsonClient(
        {search_url: fixture_json("stac/item_collection.json")}
    )
    adapter = StacAdapter(endpoint=endpoint, get_json=client)
    query = SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0), limit=2)

    results = adapter.search(query, collections=("sentinel-2",))

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
        source_type="stac",
        settings={
            "endpoint": endpoint,
            "collection_id": "sentinel-2",
            "item_id": "scene-1",
            "asset_key": "visual",
        },
    )
    assert results[0].metadata.raw["stac_version"] == "1.0.0"


def test_stac_requires_explicit_asset_key() -> None:
    """visual と thumbnail のどちらを取得するか暗黙選択しないために必要である。"""
    with pytest.raises(ConfigValidationError, match="asset_key"):
        StacAdapter(get_json=RecordingJsonClient({})).load(
            Config(
                source_type="stac",
                settings={
                    "endpoint": "https://stac.example",
                    "collection_id": "sentinel-2",
                    "item_id": "scene-1",
                },
            )
        )


def test_stac_missing_requested_asset_is_a_response_error() -> None:
    """Provider response に存在しない asset を URL 等から補完しないために必要である。"""
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})

    with pytest.raises(ProviderResponseError, match="missing"):
        StacAdapter(get_json=client).load(
            Config(
                source_type="stac",
                settings={
                    "endpoint": endpoint,
                    "collection_id": "sentinel-2",
                    "item_id": "scene-1",
                    "asset_key": "missing",
                },
            )
        )
