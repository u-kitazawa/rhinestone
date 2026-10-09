from collections.abc import Mapping
from typing import Any

import pytest

from rhinestone.adapters.source.ckan import CkanAdapter
from rhinestone.adapters.source.ogc import OgcFeaturesAdapter
from rhinestone.adapters.source.stac import StacAdapter
from rhinestone.models import Reference, SearchQuery
from rhinestone.registry import CredentialRegistry
from tests.provider_support import fixture_json


class HeaderRecordingClient:
    def __init__(self, responses: Mapping[str, Mapping[str, Any]]) -> None:
        self.responses: dict[str, Mapping[str, Any]] = dict(responses)
        self.calls: list[tuple[str, Mapping[str, Any], Mapping[str, str]]] = []

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
    adapter = CkanAdapter(
        get_json=client,
        credential="ckan",
        credentials=CredentialRegistry({"ckan": lambda: "ckan-secret"}),
    )

    source = adapter.load(
        Reference(
            "ckan", parameters={"endpoint": endpoint, "resource_id": "resource-1"}
        )
    )

    assert client.calls[0][2] == {"Authorization": "ckan-secret"}
    assert "ckan-secret" not in repr(source)


def test_ckan_credential_can_use_configured_header() -> None:
    """CKAN deploymentごとに異なるAPI-key header名を明示指定できるために必要である。"""
    endpoint = "https://catalog.example"
    url = endpoint + "/api/3/action/package_search"
    client = HeaderRecordingClient({url: fixture_json("ckan/package_search.json")})
    adapter = CkanAdapter(
        endpoint=endpoint,
        get_json=client,
        credential="ckan",
        credentials=CredentialRegistry({"ckan": lambda: "ckan-secret"}),
        credential_header="X-CKAN-API-Key",
    )

    adapter.search(SearchQuery(text="river"))

    assert client.calls[0][2] == {"X-CKAN-API-Key": "ckan-secret"}


@pytest.mark.parametrize("adapter_factory", (StacAdapter, OgcFeaturesAdapter))
def test_standard_adapters_send_bearer_token_as_header(adapter_factory: Any) -> None:
    """STAC/OGCの保護APIへBearer tokenをqueryへ露出せず送るために必要である。"""
    client = HeaderRecordingClient({})
    adapter = adapter_factory(
        get_json=client,
        credential="service",
        credentials=CredentialRegistry({"service": lambda: "bearer-secret"}),
    )
    query = SearchQuery()
    if adapter_factory is OgcFeaturesAdapter:
        adapter = adapter_factory(
            endpoint="https://features.example",
            collection_id="rivers",
            get_json=client,
            credential="service",
            credentials=CredentialRegistry({"service": lambda: "bearer-secret"}),
        )
        client.responses["https://features.example/collections/rivers/items"] = {
            "features": []
        }
    else:
        client.responses["https://stac.example/search"] = {"features": []}
        adapter = adapter_factory(
            endpoint="https://stac.example",
            get_json=client,
            credential="service",
            credentials=CredentialRegistry({"service": lambda: "bearer-secret"}),
        )

    adapter.search(query)

    assert client.calls[0][2] == {"Authorization": "Bearer bearer-secret"}
    assert "bearer-secret" not in repr(client.calls[0][1])


@pytest.mark.parametrize(
    "argument", ("api_token", "api_key", "api_key_header", "token_scheme")
)
def test_removed_direct_credentials_are_rejected(argument: str) -> None:
    with pytest.raises(TypeError, match=argument):
        kwargs: dict[str, Any] = {argument: "secret"}
        CkanAdapter(get_json=HeaderRecordingClient({}), **kwargs)


def test_unauthenticated_json_transport() -> None:
    """認証なしのmetadata取得には2引数transportを使用する。"""
    endpoint = "https://catalog.example"
    url = endpoint + "/api/3/action/package_search"
    calls: list[tuple[str, Mapping[str, Any]]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append((url, params))
        return fixture_json("ckan/package_search.json")

    CkanAdapter(endpoint=endpoint, get_json=get_json).search(SearchQuery())

    assert calls == [(url, {})]
