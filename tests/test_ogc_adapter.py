import pytest

from rhinestone.adapters.source.ogc import OgcFeaturesAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import RecordingJsonClient, fixture_json


def test_ogc_collection_items_link_becomes_service_resource() -> None:
    endpoint = "https://features.example"
    collection_url = endpoint + "/collections/rivers"
    client = RecordingJsonClient({collection_url: fixture_json("ogc/collection.json")})
    adapter = OgcFeaturesAdapter(get_json=client)
    source = adapter.load(
        Config(
            "ogc-features",
            {"endpoint": endpoint, "collection_id": "rivers"},
        )
    )
    assert client.calls == [(collection_url, {})]
    assert source.metadata.title == "Rivers"
    assert (
        source.candidates[0].uri == "https://features.example/collections/rivers/items"
    )
    assert source.candidates[0].media_type == "application/geo+json"
    assert source.candidates[0].format == "ogc-api-features"
    assert source.provenance.dataset_identifier == "rivers"
    assert source.raw_metadata["extent"]["spatial"]["bbox"][0] == (
        139.0,
        35.0,
        140.0,
        36.0,
    )


def test_ogc_search_uses_items_endpoint_and_standard_query_parameters() -> None:
    items_url = "https://features.example/collections/rivers/items"
    client = RecordingJsonClient(
        {items_url: fixture_json("ogc/feature_collection.json")}
    )
    adapter = OgcFeaturesAdapter(
        endpoint="https://features.example",
        collection_id="rivers",
        get_json=client,
    )
    results = adapter.search(SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0), limit=10))
    assert client.calls == [(items_url, {"bbox": "139.0,35.0,140.0,36.0", "limit": 10})]
    assert results[0].title == "Example River"
    assert results[0].to_config() == Config(
        "ogc-features",
        {"collection_id": "rivers", "feature_id": "river-1"},
    )
    assert "endpoint" not in results[0].target.settings
    assert results[0].metadata.raw["geometry"]["type"] == "LineString"


def test_ogc_search_requires_collection_context() -> None:
    adapter = OgcFeaturesAdapter(
        endpoint="https://features.example", get_json=RecordingJsonClient({})
    )
    with pytest.raises(ConfigValidationError, match="collection_id"):
        adapter.search(SearchQuery(limit=10))


def test_ogc_collection_without_items_link_is_rejected() -> None:
    endpoint = "https://features.example"
    collection_url = endpoint + "/collections/rivers"
    client = RecordingJsonClient(
        {
            collection_url: {
                "id": "rivers",
                "title": "Rivers",
                "links": [{"rel": "self", "href": collection_url}],
            }
        }
    )
    with pytest.raises(ProviderResponseError, match="items"):
        OgcFeaturesAdapter(get_json=client).load(
            Config(
                "ogc-features",
                {"endpoint": endpoint, "collection_id": "rivers"},
            )
        )


def test_ogc_load_encodes_identifiers_and_keeps_logical_provenance() -> None:
    endpoint = "https://features.example"
    collection_id = "river/basin?archive#v1"
    feature_id = "already%2Fencoded"
    collection_url = endpoint + "/collections/river%2Fbasin%3Farchive%23v1"
    items_url = collection_url + "/items"
    collection = dict(fixture_json("ogc/collection.json"))
    collection["links"] = [
        {"rel": "items", "type": "application/geo+json", "href": items_url}
    ]
    client = RecordingJsonClient({collection_url: collection})

    source = OgcFeaturesAdapter(get_json=client).load(
        Config(
            "ogc-features",
            {
                "endpoint": endpoint,
                "collection_id": collection_id,
                "feature_id": feature_id,
            },
        )
    )

    assert client.calls == [(collection_url, {})]
    assert source.candidates[0].uri == items_url + "/already%252Fencoded"
    assert source.candidates[0].attributes == {
        "collection_id": collection_id,
        "feature_id": feature_id,
    }
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == feature_id


def test_ogc_load_escapes_dot_only_identifier_segments() -> None:
    endpoint = "https://features.example"
    collection_url = endpoint + "/collections/%2E%2E"
    items_url = endpoint + "/collections/%2E%2E/items"
    collection = dict(fixture_json("ogc/collection.json"))
    collection["links"] = [
        {"rel": "items", "type": "application/geo+json", "href": items_url}
    ]
    client = RecordingJsonClient({collection_url: collection})

    source = OgcFeaturesAdapter(get_json=client).load(
        Config(
            "ogc-features",
            {
                "endpoint": endpoint,
                "collection_id": "..",
                "feature_id": ".",
            },
        )
    )

    assert client.calls == [(collection_url, {})]
    assert source.candidates[0].uri == items_url + "/%2E"
    assert source.provenance.dataset_identifier == ".."
    assert source.provenance.resource_identifier == "."


def test_ogc_search_result_keeps_logical_identifiers_for_encoded_load() -> None:
    endpoint = "https://features.example"
    collection_id = "river/basin"
    feature_id = "station?revision#1%"
    collection_path = "river%2Fbasin"
    items_url = endpoint + f"/collections/{collection_path}/items"
    collection_url = endpoint + f"/collections/{collection_path}"
    search_response = dict(fixture_json("ogc/feature_collection.json"))
    feature = dict(search_response["features"][0])
    feature["id"] = feature_id
    search_response["features"] = [feature]
    collection = dict(fixture_json("ogc/collection.json"))
    collection["links"] = [
        {"rel": "items", "type": "application/geo+json", "href": items_url}
    ]
    client = RecordingJsonClient(
        {items_url: search_response, collection_url: collection}
    )
    adapter = OgcFeaturesAdapter(
        endpoint=endpoint,
        collection_id=collection_id,
        get_json=client,
    )

    result = adapter.search(SearchQuery(limit=1))[0]
    source = adapter.load(result.to_config())

    assert result.target.settings["collection_id"] == collection_id
    assert result.target.settings["feature_id"] == feature_id
    assert result.provenance.dataset_identifier == collection_id
    assert result.provenance.resource_identifier == feature_id
    assert client.calls == [(items_url, {"limit": 1}), (collection_url, {})]
    assert source.candidates[0].uri == items_url + "/station%3Frevision%231%25"
    assert source.provenance.dataset_identifier == collection_id
    assert source.provenance.resource_identifier == feature_id
