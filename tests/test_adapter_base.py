import ast
import json
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, cast

import pytest
from jsonschema import Draft202012Validator

from rhinestone.adapters import (
    CkanAdapter,
    DcatAdapter,
    DirectAdapter,
    GsiFundamentalAdapter,
    OdptAdapter,
    OgcFeaturesAdapter,
    PlateauAdapter,
    ProviderAdapter,
    StacAdapter,
)
from rhinestone.adapters.source._knowledge import string
from rhinestone.errors import (
    ConfigValidationError,
    ProviderMetadataError,
    ProviderResponseError,
)
from rhinestone.models import Config, Source

ADAPTER_PACKAGES = (
    "source/ckan",
    "source/dcat",
    "source/direct",
    "source/gsi_fundamental",
    "source/odpt",
    "source/ogc",
    "source/plateau",
    "source/search_ckan_jp",
    "source/stac",
    "source/static",
    "execution/gdal",
    "execution/json_service",
    "execution/pyogrio",
    "execution/rasterio",
)


class ProbeAdapter(ProviderAdapter):
    adapter_type = "probe"

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

    def request_uri(self) -> str:
        return self._request_with_uri("https://provider.example/data", {})[1]

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
    with pytest.raises(ConfigValidationError, match="adapter type"):
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

    def programming_error(url: str, params: Mapping[str, Any]) -> Any:
        raise TypeError("transport callback bug")

    with pytest.raises(TypeError, match="transport callback bug"):
        ProbeAdapter(programming_error).request()

    def value_error(url: str, params: Mapping[str, Any]) -> Any:
        raise ValueError("transport callback bug")

    with pytest.raises(ValueError, match="transport callback bug"):
        ProbeAdapter(value_error).request()

    def response_error(url: str, params: Mapping[str, Any]) -> Any:
        raise ProviderResponseError("invalid JSON")

    with pytest.raises(ProviderResponseError, match="invalid JSON"):
        ProbeAdapter(response_error).request()

    with pytest.raises(ProviderResponseError, match="root"):
        ProbeAdapter(lambda url, params: []).request()
    with pytest.raises(ProviderResponseError, match="object"):
        ProbeAdapter(lambda url, params: {}).object([])
    with pytest.raises(ProviderResponseError, match="object or array"):
        ProbeAdapter(lambda url, params: {}).objects("invalid")
    with pytest.raises(ProviderResponseError, match="object"):
        ProbeAdapter(lambda url, params: {}).objects([{}, "invalid"])

    class InvalidResponseUri(dict[str, Any]):
        response_uri = None

    assert ProbeAdapter(lambda url, params: InvalidResponseUri()).request_uri() == (
        "https://provider.example/data"
    )


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


@pytest.mark.parametrize(
    "adapter",
    (
        CkanAdapter,
        DcatAdapter,
        DirectAdapter,
        GsiFundamentalAdapter,
        OdptAdapter,
        OgcFeaturesAdapter,
        PlateauAdapter,
        StacAdapter,
    ),
)
def test_builtin_source_adapters_implement_the_public_base(adapter: Any) -> None:
    assert issubclass(adapter, ProviderAdapter)


@pytest.mark.parametrize(
    "adapter",
    (
        CkanAdapter,
        DcatAdapter,
        DirectAdapter,
        GsiFundamentalAdapter,
        OdptAdapter,
        OgcFeaturesAdapter,
        PlateauAdapter,
        StacAdapter,
    ),
)
def test_builtin_adapter_schema_is_valid_json_schema(adapter: Any) -> None:
    package_name = adapter.__module__.rpartition(".")[0]
    text = resources.files(package_name).joinpath("schema.json").read_text()

    Draft202012Validator.check_schema(json.loads(text))


def test_internal_string_validation_remains_available_to_custom_adapters() -> None:
    with pytest.raises(ConfigValidationError, match="name"):
        string({}, "name")


@pytest.mark.parametrize("package", ADAPTER_PACKAGES)
def test_adapter_package_initializers_only_reexport_public_symbols(
    package: str,
) -> None:
    root = Path(__file__).parents[1] / "src" / "rhinestone" / "adapters"
    tree = ast.parse((root / package / "__init__.py").read_text())

    assert not any(
        isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        for node in tree.body
    )
