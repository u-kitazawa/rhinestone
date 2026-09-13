from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, cast

import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import (
    Config,
    Provider,
    configure,
    sources,
)
from rhinestone.adapters.execution.json_service import JsonServiceAdapter
from rhinestone.adapters.source.ckan import CkanAdapter
from rhinestone.adapters.source.odpt import OdptAdapter
from rhinestone.errors import (
    ConfigValidationError,
    DestinationNotAllowedError,
)
from rhinestone.models import RuntimeFactory, SearchQuery
from rhinestone.registry import CredentialRegistry
from rhinestone.security import DestinationPolicy, DestinationRule
from tests.provider_support import fixture_json


class RecordingGdal:
    def __init__(self) -> None:
        self.calls: List[str] = []

    def OpenEx(self, uri: str, **kwargs: Any) -> str:
        self.calls.append(uri)
        return "dataset"


def test_destination_rule_uses_url_boundaries() -> None:
    rule = DestinationRule.from_url("https://catalog.example/api/")
    assert rule is not None
    assert rule.matches("https://catalog.example/api")
    assert rule.matches("https://catalog.example/api/action")
    assert not rule.matches("https://catalog.example/apix")
    assert not rule.matches("http://catalog.example/api/action")
    assert not rule.matches("https://other.example/api/action")
    assert not rule.matches("not-a-url")


@pytest.mark.parametrize(
    "url",
    (
        "ftp://catalog.example/data",
        "/local/data",
        "https:///missing-host",
        "https://catalog.example:not-a-port/data",
        "https://user:pass@catalog.example/data",
        "https://exa mple/data",
        "https://%ZZ/data",
    ),
)
def test_destination_rule_rejects_non_http_or_ambiguous_urls(url: str) -> None:
    assert DestinationRule.from_url(url) is None


def test_catalog_policy_collects_nested_url_values_without_duplicates() -> None:
    provider = Provider(
        "custom",
        "static",
        {
            "endpoint": "https://catalog.example/api/",
            "nested": [
                "https://catalog.example/api",
                {"url": "https://tiles.example/{z}/{x}/{y}.png"},
            ],
        },
    )

    policy = DestinationPolicy.from_catalog((provider,))

    assert len(policy.rules) == 2
    with pytest.raises(DestinationNotAllowedError):
        policy.authorize(
            "https://catalog.example/api/action",
            credentialed=True,
            service="static",
            credential="secret",
        )
    policy.authorize("https://tiles.example/1/2/3.png")
    with pytest.raises(DestinationNotAllowedError):
        policy.authorize(
            "https://evil.example/data",
            credentialed=True,
            service="static",
            credential="secret",
        )


def test_policy_levels_control_when_authorization_is_applied() -> None:
    policy = DestinationPolicy.from_catalog(
        (Provider("source", "static", {"endpoint": "https://known.example"}),),
        level="credentialed",
    )
    policy.authorize("https://evil.example/data")
    with pytest.raises(DestinationNotAllowedError):
        policy.authorize(
            "https://evil.example/data",
            credentialed=True,
            service="static",
            credential="secret",
        )

    DestinationPolicy.unrestricted().authorize(
        "https://evil.example/data", credentialed=True
    )
    policy.authorize("file:///tmp/data", credentialed=True)
    with pytest.raises(DestinationNotAllowedError):
        policy.authorize("https://[invalid", credentialed=True)

    with pytest.raises(ConfigValidationError):
        DestinationPolicy(level="invalid")  # type: ignore[arg-type]


def test_configured_odpt_rejects_tampered_destination_before_factory() -> None:
    factory_calls: List[bool] = []

    def get_json(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: cast(List[Mapping[str, Any]], []),
        )

    app = configure(
        sources=(sources.ODPT,),
        dependencies={
            "json-service": RuntimeFactory(lambda: SimpleNamespace(get=get_json))
        },
        credentials={
            "odpt": lambda: factory_calls.append(True) or "secret",
        },
    )
    resource = app.resolve(Config("odpt", {"dataset": "station", "credential": "odpt"}))
    plan = resource.access_plan
    tampered_plan = replace(
        plan,
        uri="https://evil.example/service",
        options={**plan.options, "endpoint": "https://evil.example/service"},
    )
    tampered = replace(
        resource,
        uri="https://evil.example/service",
        access_plan=tampered_plan,
    )

    with pytest.raises(DestinationNotAllowedError):
        JsonServiceAdapter(
            OdptAdapter.prepare_request,
            "odpt",
            CredentialRegistry(
                {"odpt": lambda: factory_calls.append(True) or "secret"}
            ),
            DestinationPolicy.from_catalog((sources.ODPT,)),
        ).open(tampered, SimpleNamespace(get=get_json))
    assert factory_calls == []


def test_custom_odpt_provider_endpoint_is_authorized_by_its_catalog_entry() -> None:
    endpoint = "https://private-odpt.example/api/v4"
    calls: List[str] = []

    def get(url: str, **kwargs: Any) -> Any:
        calls.append(url)
        return SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: cast(List[Mapping[str, Any]], []),
        )

    settings = dict(sources.ODPT.settings)
    settings["endpoint"] = endpoint
    app = configure(
        sources=(Provider("private-odpt", "odpt", settings),),
        dependencies={"json-service": RuntimeFactory(lambda: SimpleNamespace(get=get))},
        credentials={"key": lambda: "secret"},
    )

    resource = app.resolve(
        Config("private-odpt", {"dataset": "station", "credential": "key"})
    )

    assert resource.open("json-service") == []
    assert calls == [endpoint + "/odpt:Station"]


def test_odpt_credential_rules_exclude_metadata_and_other_providers() -> None:
    policy = DestinationPolicy.from_catalog(
        (
            sources.ODPT,
            Provider(
                "other",
                "ckan",
                {
                    "endpoint": "https://other.example/api",
                    "credential": "other-key",
                },
            ),
        )
    )

    policy.authorize(
        "https://api.odpt.org/api/v4/odpt:Station",
        credentialed=True,
        provider="odpt",
        service="odpt",
        credential="odpt-key",
    )
    for url in (
        "https://developer.odpt.org/documents",
        "https://developer.odpt.org/terms/data_basic_license.html",
        "https://other.example/api",
    ):
        with pytest.raises(DestinationNotAllowedError):
            policy.authorize(
                url,
                credentialed=True,
                provider="odpt",
                service="odpt",
                credential="odpt-key",
            )


def test_credential_rule_requires_matching_service_and_credential() -> None:
    provider = Provider(
        "private",
        "ckan",
        {
            "endpoint": "https://catalog.example/api",
            "credential": "catalog-key",
        },
    )
    policy = DestinationPolicy.from_catalog((provider, provider))

    assert policy.credential_rules is not None
    assert len(policy.credential_rules) == 1
    policy.authorize(
        "https://catalog.example/api/action",
        credentialed=True,
        provider="private",
        service="ckan",
        credential="catalog-key",
    )
    for service, credential in (
        ("stac", "catalog-key"),
        ("ckan", "other-key"),
    ):
        with pytest.raises(DestinationNotAllowedError):
            policy.authorize(
                "https://catalog.example/api/action",
                credentialed=True,
                provider="private",
                service=service,
                credential=credential,
            )


def test_explicit_rules_remain_usable_for_direct_adapter_credentials() -> None:
    endpoint = "https://catalog.example"
    url = endpoint + "/api/3/action/package_search"
    rule = DestinationRule.from_url(endpoint)
    assert rule is not None
    calls: List[Mapping[str, str]] = []

    def get_json(
        request_url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> Mapping[str, Any]:
        assert request_url == url
        calls.append(headers)
        return fixture_json("ckan/package_search.json")

    CkanAdapter(
        get_json=get_json,
        endpoint=endpoint,
        api_token="secret",
        destination_policy=DestinationPolicy(rules=(rule,)),
    ).search(SearchQuery(text="river"))

    assert calls == [{"Authorization": "secret"}]


def test_catalog_endpoint_without_logical_credential_supports_direct_secret() -> None:
    endpoint = "https://catalog.example"
    policy = DestinationPolicy.from_catalog(
        (Provider("private", "ckan", {"endpoint": endpoint}),)
    )

    policy.authorize(
        endpoint + "/api/3/action/package_search",
        credentialed=True,
        service="ckan",
    )


def test_odpt_without_resource_types_has_no_credential_destination() -> None:
    policy = DestinationPolicy.from_catalog(
        (Provider("odpt", "odpt", {"endpoint": "https://api.example"}),)
    )

    assert policy.credential_rules == ()


def test_invalid_credential_endpoint_does_not_create_rule() -> None:
    policy = DestinationPolicy.from_catalog(
        (
            Provider(
                "private",
                "ckan",
                {"endpoint": "not-a-url", "credential": "catalog-key"},
            ),
            Provider(
                "invalid-credential",
                "ckan",
                {"endpoint": "https://catalog.example", "credential": ""},
            ),
        )
    )

    assert policy.credential_rules == ()


def test_odpt_credential_rule_is_scoped_to_provider_and_resource_path() -> None:
    endpoint = "https://shared.example/api/v4"
    settings = dict(sources.ODPT.settings)
    settings["endpoint"] = endpoint
    policy = DestinationPolicy.from_catalog(
        (Provider("private-odpt", "odpt", settings),)
    )

    for provider, url in (
        ("odpt", endpoint + "/odpt:Station"),
        ("private-odpt", endpoint + "/documentation"),
        ("private-odpt", endpoint + "/odpt:Unknown"),
    ):
        with pytest.raises(DestinationNotAllowedError):
            policy.authorize(
                url,
                credentialed=True,
                provider=provider,
                service="odpt",
                credential="key",
            )


def test_tampered_odpt_catalog_url_does_not_evaluate_credential_factory() -> None:
    credential_calls: List[bool] = []
    runtime_calls: List[bool] = []
    app = configure(
        sources=(sources.ODPT, sources.GSI),
        credentials={
            "odpt": lambda: credential_calls.append(True) or "secret",
        },
    )
    resource = app.resolve(Config("odpt", {"dataset": "station", "credential": "odpt"}))
    metadata_url = "https://maps.gsi.go.jp/development/ichiran.html"
    tampered = replace(
        resource,
        uri=metadata_url,
        access_plan=replace(
            resource.access_plan,
            uri=metadata_url,
            options={**resource.access_plan.options, "endpoint": metadata_url},
        ),
    )

    class Runtime:
        def get(self, *args: Any, **kwargs: Any) -> Any:
            runtime_calls.append(True)
            raise AssertionError("runtime must not be called")

    with pytest.raises(DestinationNotAllowedError):
        JsonServiceAdapter(
            OdptAdapter.prepare_request,
            "odpt",
            CredentialRegistry(
                {"odpt": lambda: credential_calls.append(True) or "secret"}
            ),
            DestinationPolicy.from_catalog((sources.ODPT, sources.GSI)),
        ).open(tampered, Runtime())

    assert credential_calls == []
    assert runtime_calls == []


@pytest.mark.parametrize(
    ("adapter_type", "endpoint", "response_path", "response", "expected_header"),
    (
        (
            "ckan",
            "https://ckan.example",
            "/api/3/action/package_search",
            fixture_json("ckan/package_search.json"),
            "secret",
        ),
        (
            "stac",
            "https://stac.example",
            "/search",
            fixture_json("stac/item_collection.json"),
            "Bearer secret",
        ),
        (
            "ogc-features",
            "https://ogc.example",
            "/collections/rivers/items",
            fixture_json("ogc/feature_collection.json"),
            "Bearer secret",
        ),
    ),
)
def test_public_http_sources_bind_credentials_lazily(
    monkeypatch: pytest.MonkeyPatch,
    adapter_type: str,
    endpoint: str,
    response_path: str,
    response: Mapping[str, Any],
    expected_header: str,
) -> None:
    calls: List[Mapping[str, str]] = []
    factory_calls: List[bool] = []

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        assert url == endpoint + response_path
        calls.append(headers or {})
        return response

    monkeypatch.setattr(_http, "get_json", get_json)
    settings: Dict[str, Any] = {"endpoint": endpoint, "credential": "secret"}
    if adapter_type == "ogc-features":
        settings["collection_id"] = "rivers"
    app = configure(
        sources=(Provider("protected", adapter_type, settings),),
        credentials={
            "secret": lambda: factory_calls.append(True) or "secret",
        },
    )
    assert factory_calls == []

    results = app.search(SearchQuery())

    assert results
    assert factory_calls == [True]
    assert calls == [{"Authorization": expected_header}]


def test_configured_source_endpoint_cannot_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: List[bool] = []

    def get_json(*args: Any, **kwargs: Any) -> Mapping[str, Any]:
        calls.append(True)
        return fixture_json("ckan/package_search.json")

    monkeypatch.setattr(_http, "get_json", get_json)
    app = configure(
        sources=(
            Provider(
                "protected",
                "ckan",
                {"endpoint": "https://known.example", "credential": "secret"},
            ),
        ),
        credentials={"secret": lambda: "secret"},
    )

    with pytest.raises(ConfigValidationError, match="managed"):
        app.resolve(
            Config(
                "protected",
                {"endpoint": "https://evil.example", "resource_id": "resource-1"},
            )
        )
    assert calls == []


def test_direct_source_adapter_can_use_a_destination_policy() -> None:
    endpoint = "https://catalog.example"
    adapter = CkanAdapter(
        get_json=lambda url, params: {},
        endpoint=endpoint,
        credential="secret",
        credentials=CredentialRegistry({"secret": lambda: "secret"}),
        destination_policy=DestinationPolicy.from_catalog(
            (Provider("catalog", "ckan", {"endpoint": endpoint}),)
        ),
    )
    with pytest.raises(DestinationNotAllowedError):
        adapter._request("https://evil.example/data", {})  # type: ignore[reportPrivateUsage]


def test_source_credential_configuration_is_validated() -> None:
    with pytest.raises(ConfigValidationError, match="non-empty string"):
        CkanAdapter(get_json=lambda url, params: {}, credential="")
    with pytest.raises(ConfigValidationError, match="either credential"):
        CkanAdapter(get_json=lambda url, params: {}, credential="name", api_token="x")
    with pytest.raises(ConfigValidationError, match="credential_header"):
        CkanAdapter(
            get_json=lambda url, params: {}, credential="name", credential_header=""
        )
    with pytest.raises(ConfigValidationError, match="credential_scheme"):
        CkanAdapter(
            get_json=lambda url, params: {},
            credential="name",
            credential_scheme=1,  # type: ignore[arg-type]
        )
    adapter = CkanAdapter(
        get_json=lambda url, params: {}, endpoint="https://known.example"
    )
    with pytest.raises(ConfigValidationError, match="should be non-empty"):
        adapter.load(Config("ckan", {"endpoint": "", "resource_id": "x"}))
    with pytest.raises(ConfigValidationError, match="non-empty string"):
        adapter._endpoint_from({"endpoint": 1})  # type: ignore[reportPrivateUsage]
    with pytest.raises(ConfigValidationError, match="managed"):
        adapter.load(
            Config(
                "ckan",
                {"endpoint": "https://evil.example", "resource_id": "x"},
            )
        )


def test_configure_supports_none_network_policy() -> None:
    class Rasterio:
        def open(self, uri: str, driver: str | None = None) -> str:
            return uri

    config = Config(
        "direct",
        {"uri": "https://unlisted.example/data.tif", "format": "geotiff"},
    )
    unrestricted = configure(
        network_policy="none", dependencies={"rasterio": Rasterio()}
    )
    assert unrestricted.open(config, "rasterio") == "https://unlisted.example/data.tif"


def test_configure_rejects_invalid_network_policy() -> None:
    with pytest.raises(ConfigValidationError, match="network policy"):
        configure(network_policy="invalid")  # type: ignore[arg-type]
