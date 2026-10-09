import pytest

from rhinestone._composition import (  # pyright: ignore[reportPrivateUsage]
    ConfiguredSourceAdapter,
)
from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, Reference, SearchQuery
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
        Reference.from_config(
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


def test_stac_search_isolates_items_without_one_data_asset() -> None:
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"

    def item(item_id: str, assets: dict[str, object]) -> dict[str, object]:
        return {
            "id": item_id,
            "collection": "imagery",
            "properties": {"title": item_id},
            "assets": assets,
        }

    response = {
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
    assert [diagnostic.resource_identifier for diagnostic in results.diagnostics] == [
        "missing",
    ]
    assert [diagnostic.detail for diagnostic in results.diagnostics] == [
        "missing_data_asset",
    ]


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
            Reference.from_config(
                Config(
                    "stac",
                    {
                        "endpoint": "https://stac.example",
                        "collection_id": "sentinel-2",
                        "item_id": "scene-1",
                    },
                )
            )
        )


def test_stac_missing_requested_asset_is_a_response_error() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/sentinel-2/items/scene-1"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})
    with pytest.raises(ProviderResponseError, match="missing"):
        StacAdapter(get_json=client).load(
            Reference.from_config(
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
        Reference.from_config(
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
        Reference.from_config(
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
        Reference.from_config(
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
    )

    assert client.calls == [(item_url, {})]
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == f"{item_id}:visual"


def test_stac_load_escapes_dot_only_identifier_segments() -> None:
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/%2E/items/%2E%2E"
    client = RecordingJsonClient({item_url: fixture_json("stac/item.json")})

    source = StacAdapter(get_json=client).load(
        Reference.from_config(
            Config(
                "stac",
                {
                    "endpoint": endpoint,
                    "collection_id": ".",
                    "item_id": "..",
                    "asset_key": "visual",
                },
            )
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
