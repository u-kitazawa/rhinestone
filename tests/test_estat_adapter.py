import pytest

from rhinestone.adapters.source.estat import EStatAdapter
from rhinestone.errors import ConfigValidationError, ProviderResponseError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import RecordingJsonClient, fixture_json


def test_estat_accepts_api_key_alias() -> None:
    adapter = EStatAdapter(api_key="app-key", get_json=RecordingJsonClient({}))
    assert getattr(adapter, "_app_id") == "app-key"


def test_estat_rejects_missing_callback_and_conflicting_credentials() -> None:
    with pytest.raises(ConfigValidationError, match="get_json"):
        EStatAdapter(app_id="app-id")
    with pytest.raises(ConfigValidationError):
        EStatAdapter(
            app_id="app-id", api_key="key", get_json=RecordingJsonClient({})
        )
    with pytest.raises(ConfigValidationError, match="credential"):
        EStatAdapter(get_json=RecordingJsonClient({})).search(SearchQuery())


def test_estat_credential_factory_is_lazy_and_used_for_requests() -> None:
    endpoint = "https://api.e-stat.go.jp/rest/3.0/app/json"
    search_url = endpoint + "/getStatsList"
    client = RecordingJsonClient(
        {search_url: fixture_json("estat/get_stats_list.json")}
    )
    calls = []

    def credential() -> str:
        calls.append(True)
        return "factory-app-id"

    adapter = EStatAdapter(credential_factory=credential, get_json=client)
    assert calls == []
    adapter.search(SearchQuery(limit=1))
    assert calls == [True]
    assert client.calls[0][1]["appId"] == "factory-app-id"


def test_estat_metadata_response_becomes_service_source_without_leaking_app_id() -> None:
    endpoint = "https://api.e-stat.go.jp/rest/3.0/app/json"
    metadata_url = endpoint + "/getMetaInfo"
    client = RecordingJsonClient(
        {metadata_url: fixture_json("estat/get_meta_info.json")}
    )
    adapter = EStatAdapter(app_id="secret-app-id", get_json=client)
    source = adapter.load(Config("estat", {"stats_data_id": "0000000001"}))
    assert client.calls == [
        (
            metadata_url,
            {
                "appId": "secret-app-id",
                "statsDataId": "0000000001",
                "lang": "J",
            },
        )
    ]
    assert source.metadata.title == "年齢別人口"
    assert source.metadata.publisher == "総務省"
    assert source.provenance.dataset_identifier == "0000000001"
    assert "secret-app-id" not in repr(source.provenance)
    assert source.candidates[0].format == "estat-api"
    assert source.candidates[0].attributes["stats_data_id"] == "0000000001"
    assert (
        source.raw_metadata["METADATA_INF"]["CLASS_INF"]["CLASS_OBJ"][0]["@id"]
        == "area"
    )


def test_estat_search_maps_text_and_limit_to_official_parameter_names() -> None:
    endpoint = "https://api.e-stat.go.jp/rest/3.0/app/json"
    search_url = endpoint + "/getStatsList"
    client = RecordingJsonClient(
        {search_url: fixture_json("estat/get_stats_list.json")}
    )
    adapter = EStatAdapter(app_id="secret-app-id", get_json=client)
    results = adapter.search(SearchQuery(text="人口", limit=10))
    assert client.calls == [
        (
            search_url,
            {
                "appId": "secret-app-id",
                "searchWord": "人口",
                "limit": 10,
                "lang": "J",
            },
        )
    ]
    assert results[0].title == "年齢別人口"
    assert results[0].to_config() == Config("estat", {"stats_data_id": "0000000001"})
    assert "secret-app-id" not in repr(results[0].provenance)


def test_estat_nonzero_result_status_is_rejected() -> None:
    endpoint = "https://api.e-stat.go.jp/rest/3.0/app/json"
    metadata_url = endpoint + "/getMetaInfo"
    client = RecordingJsonClient(
        {
            metadata_url: {
                "GET_META_INFO": {
                    "RESULT": {
                        "STATUS": 100,
                        "ERROR_MSG": "認証に失敗しました。",
                    }
                }
            }
        }
    )
    with pytest.raises(ProviderResponseError, match="認証"):
        EStatAdapter(app_id="invalid", get_json=client).load(
            Config("estat", {"stats_data_id": "0000000001"})
        )
