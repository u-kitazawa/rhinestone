from typing import Any, Mapping, cast

import pytest

from rhinestone.adapters import ProviderAdapter
from rhinestone.errors import (
    ConfigValidationError,
    ProviderMetadataError,
    ProviderResponseError,
)
from rhinestone.models import Config, Source


class ProbeAdapter(ProviderAdapter):
    source_type = "probe"

    def load(self, config: Config) -> Source:
        raise NotImplementedError

    def settings(self, config: Config) -> Mapping[str, Any]:
        return self._config_settings(config)

    def endpoint(self, settings: Mapping[str, Any]) -> str:
        return self._endpoint_from(settings)

    def required(self, settings: Mapping[str, Any], name: str) -> str:
        return self._required_string(settings, name)

    def request(self) -> Mapping[str, Any]:
        return self._request("https://provider.example/data", {})

    def object(self, value: Any) -> Mapping[str, Any]:
        return self._object(value, "value")

    def objects(self, value: Any):
        return self._objects(value, "values")


def test_common_adapter_normalizes_endpoint_and_validates_config() -> None:
    """全providerでsource type、必須文字列、endpointの検証を一貫させるために必要である。"""
    adapter = ProbeAdapter(lambda url, params: {}, endpoint="https://example.test/")

    assert adapter.endpoint({}) == "https://example.test"
    assert adapter.required({"id": "known"}, "id") == "known"
    assert adapter.settings(Config("probe", {"id": "known"}))["id"] == "known"
    with pytest.raises(ConfigValidationError, match="source_type"):
        adapter.settings(Config("other", {}))
    with pytest.raises(ConfigValidationError, match="endpoint"):
        ProbeAdapter(lambda url, params: {}).endpoint({})
    with pytest.raises(ConfigValidationError, match="id"):
        adapter.required({"id": 1}, "id")


def test_common_adapter_wraps_transport_failure_and_validates_json_shapes() -> None:
    """通信失敗とprovider schema不正を原因別エラーへ統一するために必要である。"""
    transport_error = OSError("offline")

    def fail(url: str, params: Mapping[str, Any]) -> Any:
        raise transport_error

    with pytest.raises(ProviderMetadataError) as captured:
        ProbeAdapter(fail).request()
    assert captured.value.__cause__ is transport_error

    with pytest.raises(ProviderResponseError, match="root"):
        ProbeAdapter(lambda url, params: []).request()
    with pytest.raises(ProviderResponseError, match="object"):
        ProbeAdapter(lambda url, params: {}).object([])
    with pytest.raises(ProviderResponseError, match="object or array"):
        ProbeAdapter(lambda url, params: {}).objects("invalid")
    with pytest.raises(ProviderResponseError, match="object"):
        ProbeAdapter(lambda url, params: {}).objects([{}, "invalid"])


def test_common_adapter_accepts_single_object_as_one_item_sequence() -> None:
    """単件時にobjectへ縮退するprovider JSON表現を決定的に正規化するために必要である。"""
    adapter = ProbeAdapter(lambda url, params: {})

    assert adapter.objects({"id": "one"}) == ({"id": "one"},)


def test_public_base_class_requires_load_implementation() -> None:
    """正式な基底契約を継承した具象Adapterがloadを実装し忘れないために必要である。"""

    class IncompleteAdapter(ProviderAdapter):
        pass

    def empty_get_json(url: str, params: Mapping[str, Any]) -> Mapping[str, Any]:
        return {}

    with pytest.raises(TypeError, match="abstract"):
        cast(Any, IncompleteAdapter)(empty_get_json)
