from datetime import datetime, timezone

import pytest

from rhinestone.adapters.source.ckan import CkanAdapter
from rhinestone.adapters.source.estat import EStatAdapter
from rhinestone.adapters.source.ogc import OgcFeaturesAdapter
from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import RecordingJsonClient


def test_ckan_rejects_missing_result_and_nonstandard_conditions() -> None:
    """CKANの欠損schemaと未対応検索条件をsilent fallbackしないために必要である。"""
    endpoint = "https://catalog.example"
    resource_url = endpoint + "/api/3/action/resource_show"
    adapter = CkanAdapter(
        get_json=RecordingJsonClient({resource_url: {"success": True}}),
        endpoint=endpoint,
    )

    with pytest.raises(ProviderResponseError, match="result"):
        adapter.load(Config("ckan", {"resource_id": "one"}))
    with pytest.raises(ConfigValidationError, match="bbox"):
        adapter.search(SearchQuery(bbox=(0.0, 0.0, 1.0, 1.0)))


def test_ckan_handles_unstructured_error_and_optional_metadata() -> None:
    """CKAN extension fieldがないresponseでも安定し、非object errorも明示するために必要である。"""
    endpoint = "https://catalog.example"
    resource_url = endpoint + "/api/3/action/resource_show"
    package_url = endpoint + "/api/3/action/package_show"
    failure = CkanAdapter(
        get_json=RecordingJsonClient(
            {resource_url: {"success": False, "error": "failure"}}
        )
    )
    with pytest.raises(ProviderResponseError, match="unknown"):
        failure.load(Config("ckan", {"endpoint": endpoint, "resource_id": "one"}))

    client = RecordingJsonClient(
        {
            resource_url: {
                "success": True,
                "result": {"id": "one", "package_id": "set", "url": "https://f"},
            },
            package_url: {"success": True, "result": {"id": "set"}},
        }
    )
    source = CkanAdapter(get_json=client).load(
        Config("ckan", {"endpoint": endpoint, "resource_id": "one"})
    )
    assert source.metadata.publisher is None
    assert source.candidates[0].format is None


def test_ckan_empty_query_omits_optional_action_parameters() -> None:
    """未指定の検索条件を空値としてproviderへ送信しないために必要である。"""
    endpoint = "https://catalog.example"
    search_url = endpoint + "/api/3/action/package_search"
    client = RecordingJsonClient(
        {search_url: {"success": True, "result": {"results": []}}}
    )

    assert CkanAdapter(endpoint=endpoint, get_json=client).search(SearchQuery()) == ()
    assert client.calls == [(search_url, {})]


def test_estat_validates_constructor_and_optional_search_parameters() -> None:
    """e-Stat認証・言語と未対応条件をrequest送信前に拒否するために必要である。"""
    with pytest.raises(ConfigValidationError, match="app_id"):
        EStatAdapter(app_id="", get_json=RecordingJsonClient({}))
    with pytest.raises(ConfigValidationError, match="language"):
        EStatAdapter(app_id="id", language="X", get_json=RecordingJsonClient({}))
    adapter = EStatAdapter(app_id="id", get_json=RecordingJsonClient({}))
    with pytest.raises(ConfigValidationError, match="bbox"):
        adapter.search(SearchQuery(bbox=(0.0, 0.0, 1.0, 1.0)))


def test_estat_empty_query_and_scalar_title_are_supported() -> None:
    """任意条件を省略し、単純文字列として返る日本語fieldも保持するために必要である。"""
    endpoint = "https://api.e-stat.go.jp/rest/3.0/app/json"
    search_url = endpoint + "/getStatsList"
    client = RecordingJsonClient(
        {
            search_url: {
                "GET_STATS_LIST": {
                    "RESULT": {"STATUS": 0},
                    "DATALIST_INF": {
                        "TABLE_INF": {"@id": "one", "TITLE": "Scalar title"}
                    },
                }
            }
        }
    )

    results = EStatAdapter(app_id="id", get_json=client).search(SearchQuery())

    assert results[0].title == "Scalar title"
    assert results[0].metadata.publisher is None
    assert client.calls == [(search_url, {"appId": "id", "lang": "J"})]


def test_stac_serializes_interval_and_rejects_ambiguous_data_assets() -> None:
    """STAC時間条件を標準intervalへ変換し、複数data assetを推測選択しないために必要である。"""
    endpoint = "https://stac.example"
    search_url = endpoint + "/search"
    response = {
        "features": [
            {
                "id": "item",
                "collection": "collection",
                "properties": {},
                "assets": {
                    "thumbnail": {"href": "https://thumb", "roles": ["thumbnail"]},
                    "a": {"href": "https://a", "roles": ["data"]},
                    "b": {"href": "https://b", "roles": ["data"]},
                },
            }
        ]
    }
    client = RecordingJsonClient({search_url: response})
    adapter = StacAdapter(endpoint=endpoint, get_json=client)
    query = SearchQuery(time=(datetime(2024, 1, 1, tzinfo=timezone.utc), None))

    with pytest.raises(ProviderResponseError, match="exactly one"):
        adapter.search(query)
    assert client.calls[0][1]["datetime"] == "2024-01-01T00:00:00+00:00/.."
    with pytest.raises(ConfigValidationError, match="text"):
        adapter.search(SearchQuery(text="unsupported"))


def test_stac_asset_without_media_type_remains_explicitly_unknown() -> None:
    """STAC asset hrefのsuffixから未提示format/media typeを推測しないために必要である。"""
    endpoint = "https://stac.example"
    item_url = endpoint + "/collections/c/items/i"
    client = RecordingJsonClient(
        {
            item_url: {
                "id": "i",
                "properties": {},
                "assets": {"data": {"href": "https://f.tif"}},
            }
        }
    )

    source = StacAdapter(get_json=client).load(
        Config(
            "stac",
            {
                "endpoint": endpoint,
                "collection_id": "c",
                "item_id": "i",
                "asset_key": "data",
            },
        )
    )

    assert source.candidates[0].format is None
    assert source.candidates[0].media_type is None


def test_ogc_serializes_interval_and_preserves_explicit_feature_id() -> None:
    """OGC datetime queryと明示feature idをservice accessへ保持するために必要である。"""
    endpoint = "https://features.example"
    collection_url = endpoint + "/collections/rivers"
    items_url = endpoint + "/collections/rivers/items"
    client = RecordingJsonClient(
        {
            collection_url: {
                "id": "rivers",
                "links": [{"rel": "items", "href": items_url}],
            },
            items_url: {"features": []},
        }
    )
    adapter = OgcFeaturesAdapter(
        endpoint=endpoint, collection_id="rivers", get_json=client
    )
    source = adapter.load(
        Config(
            "ogc-features",
            {"endpoint": endpoint, "collection_id": "rivers", "feature_id": "r1"},
        )
    )
    assert source.candidates[0].uri == items_url + "/r1"

    adapter.search(SearchQuery(time=(None, datetime(2024, 1, 2, tzinfo=timezone.utc))))
    assert client.calls[-1][1]["datetime"] == "../2024-01-02T00:00:00+00:00"
    with pytest.raises(ConfigValidationError, match="text"):
        adapter.search(SearchQuery(text="unsupported"))


def test_ogc_feature_without_title_uses_stable_identifier() -> None:
    """任意title/nameがないFeatureでもprovider識別子を失わず検索結果を作るために必要である。"""
    endpoint = "https://features.example"
    items_url = endpoint + "/collections/rivers/items"
    client = RecordingJsonClient(
        {items_url: {"features": [{"id": "r1", "properties": {}}]}}
    )
    adapter = OgcFeaturesAdapter(
        endpoint=endpoint, collection_id="rivers", get_json=client
    )

    assert adapter.search(SearchQuery())[0].title == "r1"
