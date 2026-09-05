from typing import Any, Dict, List, Mapping, Tuple

import pytest

from rhinestone.adapters.source.ckan import CkanAdapter
from rhinestone.adapters.source.ogc import OgcFeaturesAdapter
from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.errors import ConfigValidationError
from rhinestone.models import Config, SearchQuery
from tests.provider_support import fixture_json


class HeaderRecordingClient:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses: Dict[str, Mapping[str, Any]] = dict(responses)
        self.calls: List[Tuple[str, Mapping[str, Any], Mapping[str, str]]] = []

    def __call__(
        self,
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> Mapping[str, Any]:
        self.calls.append((url, dict(params), dict(headers)))
        return self.responses[url]


def test_ckan_api_token_uses_authorization_header_without_provenance_leak() -> None:
    """CKAN公式のAuthorization tokenを送信しつつsecretをSource知識へ保存しないために必要である。"""
    endpoint = "https://catalog.example"
    resource_url = endpoint + "/api/3/action/resource_show"
    package_url = endpoint + "/api/3/action/package_show"
    client = HeaderRecordingClient(
        {
            resource_url: fixture_json("ckan/resource_show.json"),
            package_url: fixture_json("ckan/package_show.json"),
        }
    )
    adapter = CkanAdapter(get_json=client, api_token="ckan-secret")

    source = adapter.load(
        Config("ckan", {"endpoint": endpoint, "resource_id": "resource-1"})
    )

    assert client.calls[0][2] == {"Authorization": "ckan-secret"}
    assert "ckan-secret" not in repr(source)


def test_ckan_legacy_api_key_can_use_configured_header() -> None:
    """CKAN deploymentごとに異なるAPI-key header名を明示指定できるために必要である。"""
    endpoint = "https://catalog.example"
    url = endpoint + "/api/3/action/package_search"
    client = HeaderRecordingClient({url: fixture_json("ckan/package_search.json")})
    adapter = CkanAdapter(
        endpoint=endpoint,
        get_json=client,
        api_key="legacy-secret",
        api_key_header="X-CKAN-API-Key",
    )

    adapter.search(SearchQuery(text="river"))

    assert client.calls[0][2] == {"X-CKAN-API-Key": "legacy-secret"}


@pytest.mark.parametrize("adapter_factory", (StacAdapter, OgcFeaturesAdapter))
def test_standard_adapters_send_bearer_token_as_header(adapter_factory: Any) -> None:
    """STAC/OGCの保護APIへBearer tokenをqueryへ露出せず送るために必要である。"""
    client = HeaderRecordingClient({})
    adapter = adapter_factory(get_json=client, api_token="bearer-secret")
    query = SearchQuery()
    if adapter_factory is OgcFeaturesAdapter:
        adapter = adapter_factory(
            endpoint="https://features.example",
            collection_id="rivers",
            get_json=client,
            api_token="bearer-secret",
        )
        client.responses["https://features.example/collections/rivers/items"] = {
            "features": []
        }
    else:
        client.responses["https://stac.example/search"] = {"features": []}
        adapter = adapter_factory(
            endpoint="https://stac.example",
            get_json=client,
            api_token="bearer-secret",
        )

    adapter.search(query)

    assert client.calls[0][2] == {"Authorization": "Bearer bearer-secret"}
    assert "bearer-secret" not in repr(client.calls[0][1])


def test_token_and_key_are_mutually_exclusive() -> None:
    """認証情報の優先順位を暗黙に決めず、誤送信を防ぐために必要である。"""
    with pytest.raises(ConfigValidationError, match="both"):
        CkanAdapter(
            get_json=HeaderRecordingClient({}),
            api_token="token",
            api_key="key",
        )


@pytest.mark.parametrize(
    "kwargs",
    ({"api_token": ""}, {"api_key": ""}, {"api_key": "secret", "api_key_header": ""}),
)
def test_empty_credentials_are_rejected(kwargs: Mapping[str, Any]) -> None:
    with pytest.raises(ConfigValidationError):
        CkanAdapter(get_json=HeaderRecordingClient({}), **kwargs)


def test_two_argument_json_callback_remains_supported_without_auth() -> None:
    """既存利用者の2引数transport callbackを認証なしでは壊さないために必要である。"""
    endpoint = "https://catalog.example"
    url = endpoint + "/api/3/action/package_search"
    calls: List[Tuple[str, Mapping[str, Any]]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append((url, params))
        return fixture_json("ckan/package_search.json")

    CkanAdapter(endpoint=endpoint, get_json=get_json).search(SearchQuery())

    assert calls == [(url, {})]
