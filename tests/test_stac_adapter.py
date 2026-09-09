import pytest

from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import RecordingJsonClient, fixture_json


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


def test_stac_load_encodes_identifiers_as_individual_path_segments() -> None:
    endpoint = "https://stac.example"
    collection_id = "sentinel/2?archive#v1"
    item_id = "already%2Fencoded"
    item_url = (
        endpoint + "/collections/sentinel%2F2%3Farchive%23v1/items/already%252Fencoded"
    )
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})

    source = StacAdapter(get_json=client).load(
        Config(
            "stac",
            {
                "endpoint": endpoint,
                "collection_id": collection_id,
                "item_id": item_id,
                "asset_key": "visual",
            },
        )
    )

    assert client.calls == [(item_url, {})]
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == item_id


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
    source = adapter.load(result.to_config())

    assert result.target.settings["collection_id"] == collection_id
    assert result.target.settings["item_id"] == item_id
    assert result.provenance.dataset_identifier == collection_id
    assert result.provenance.resource_identifier == item_id
    assert client.calls == [(search_url, {"limit": 1}), (item_url, {})]
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == item_id
