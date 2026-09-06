"""Executable provider contracts and failures for the four expansion adapters."""

import importlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, cast

import pytest

from rhinestone import Config, SearchQuery, configure, sources
from rhinestone.adapters import (
    DcatAdapter,
    GsiFundamentalAdapter,
    OdptAdapter,
    PlateauAdapter,
)
from rhinestone.adapters.execution import GdalAdapter, JsonServiceAdapter
from rhinestone.errors import (
    AmbiguousResourceError,
    ConfigValidationError,
    CredentialLoadError,
    CredentialUnavailableError,
    ProviderMetadataError,
    ProviderResponseError,
    ResourceAccessError,
    ResourceNotFoundError,
    UnsupportedAccessError,
    UnsupportedSearchConditionError,
)
from rhinestone.models import ResourceCandidate, ServiceQueryPlan
from rhinestone.registry import CredentialRegistry
from rhinestone.resolution import Resolver
from tests.provider_support import fixture_json
from tests.test_resolution import make_source

FIXTURES = Path(__file__).parent / "fixtures" / "expansion"



def fail(*args: Any, **kwargs: Any) -> Any:
    raise ValueError("secret-in-underlying-error")



def test_dcat_rejects_an_unsupported_serialization_before_loading() -> None:
    adapter = DcatAdapter(
        lambda uri: "",
        lambda: None,
        catalog_uri="https://example.test/catalog",
        serialization="n3",
    )

    with pytest.raises(ConfigValidationError, match="serialization"):
        adapter.search(SearchQuery())


def plateau_client(url: str, params: Mapping[str, Any]) -> Any:
    package = fixture_json("expansion/plateau.json")
    if url.endswith("resource_show"):
        return {"success": True, "result": package["result"]["resources"][0]}
    if url.endswith("package_search"):
        return {"success": True, "result": {"results": [package["result"]]}}
    return package


def test_plateau_requires_catalog_endpoint() -> None:
    with pytest.raises(ConfigValidationError, match="endpoint"):
        PlateauAdapter(plateau_client)


def test_plateau_preserves_all_candidates_and_explicit_archive_selection() -> None:
    adapter = PlateauAdapter(plateau_client, endpoint="https://fixture.example")
    settings = {
        "resource_id": "citygml",
        "archive": "zip",
        "entry_point": "udx/bldg/city.gml",
    }
    item = adapter.load(Config("plateau", settings))
    assert len(item.candidates) == 2
    assert item.candidates[1].attributes["matches_config"] is False
    resource = Resolver().resolve(item)
    assert resource.format == "citygml"
    assert resource.access_plan.kind == "file"
    assert resource.access_plan.options["entry_point"] == "udx/bldg/city.gml"
    assert item.raw_metadata["package"]["extras"][0]["value"] == "2023"
    assert "distribution_provider" in resource.provenance.raw
    captured: Dict[str, Any] = {}

    def open_ex(uri: str, **kwargs: Any) -> str:
        captured["uri"] = uri
        return "city"

    assert GdalAdapter().open(resource, SimpleNamespace(OpenEx=open_ex)) == "city"
    assert (
        captured["uri"]
        == "/vsizip//vsicurl/https://fixture.example/city.zip/udx/bldg/city.gml"
    )
    found = adapter.search(SearchQuery(text="都市"))
    assert found[0].to_config().source_id == "plateau"
    assert Resolver().resolve(adapter.load(found[0].to_config())).format == "citygml"


def test_plateau_selection_is_decided_by_resolver() -> None:
    adapter = PlateauAdapter(plateau_client, endpoint="https://fixture.example")
    with pytest.raises(AmbiguousResourceError):
        Resolver().resolve(adapter.load(Config("plateau", {"dataset_id": "fixture"})))
    resource = Resolver().resolve(
        adapter.load(
            Config(
                "plateau",
                {
                    "dataset_id": "fixture",
                    "format": "gpkg",
                },
            )
        )
    )
    assert resource.format == "gpkg"
    with pytest.raises(ResourceNotFoundError):
        Resolver().resolve(
            adapter.load(
                Config(
                    "plateau",
                    {
                        "dataset_id": "fixture",
                        "format": "unknown",
                    },
                )
            )
        )


@pytest.mark.parametrize(
    "settings",
    [
        {"archive": "tar"},
        {"archive": "zip"},
        {"entry_point": "x.gml"},
        {"archive": "zip", "entry_point": "/absolute.gml"},
        {"archive": "zip", "entry_point": "../outside.gml"},
        {"archive": "zip", "entry_point": "dir\\file.gml"},
    ],
)
def test_plateau_rejects_unsafe_or_incomplete_archive_selection(
    settings: Mapping[str, Any],
) -> None:
    with pytest.raises(ConfigValidationError):
        PlateauAdapter(plateau_client, endpoint="https://fixture.example").load(
            Config("plateau", dict(settings, dataset_id="fixture"))
        )


def fundamental_settings() -> Dict[str, Any]:
    return {
        "path": str(FIXTURES / "basic.xml"),
        "dataset": "basic",
        "metadata": {
            "mesh": "533945",
            "feature_type": "BldA",
            "schema_version": "test-schema",
            "download_spec_version": "test-spec",
            "crs": "EPSG:6668",
            "source_url": "https://service.gsi.go.jp/kiban/",
        },
    }


def test_fundamental_local_source_preserves_explicit_crs() -> None:
    settings = fundamental_settings()
    config = Config("gsi-fundamental", settings)
    settings["metadata"]["crs"] = "changed-after-config"
    item = GsiFundamentalAdapter().load(config)
    resource = Resolver().resolve(item)
    assert resource.access_plan.kind == "file"
    assert resource.format == "gml"
    assert resource.metadata.raw["crs"] == "EPSG:6668"
    assert resource.source.raw_metadata["schema_version"] == "test-schema"
    assert "search" not in item.capabilities


@pytest.mark.parametrize(
    "changes,error",
    [
        ({"dataset": "dem"}, ConfigValidationError),
        ({"path": "/nonexistent/fgd.xml"}, ResourceNotFoundError),
        ({"metadata": []}, ConfigValidationError),
        ({"metadata": {}}, ConfigValidationError),
        ({"archive": "tar"}, ConfigValidationError),
        ({"entry_point": "basic.xml"}, ConfigValidationError),
    ],
)
def test_fundamental_does_not_guess_missing_knowledge(
    changes: Mapping[str, Any], error: Any
) -> None:
    settings = fundamental_settings()
    settings.update(changes)
    with pytest.raises(error):
        GsiFundamentalAdapter().load(Config("gsi-fundamental", settings))


def dcat_adapter(document: Any = None) -> DcatAdapter:
    text = (FIXTURES / "catalog.ttl").read_text() if document is None else document
    return DcatAdapter(
        lambda uri: text,
        lambda: importlib.import_module("rdflib"),
        catalog_uri="https://fixture.example/catalog",
    )


def dcat_config(**settings: Any) -> Config:
    return Config(
        "dcat",
        dict(
            {
                "uri": "https://fixture.example/catalog",
                "dataset": "https://fixture.example/dataset",
            },
            **settings,
        ),
    )


def test_dcat_preserves_rdf_and_excludes_landing_pages() -> None:
    adapter = dcat_adapter()
    item = adapter.load(dcat_config(distribution="https://fixture.example/geojson"))
    assert len(item.candidates) == 2
    resource = Resolver().resolve(item)
    assert resource.format == "geojson"
    assert resource.metadata.title == "河川"
    assert resource.metadata.license == "https://fixture.example/license"
    assert "accessURL" in resource.source.raw_metadata["document"]
    with pytest.raises(AmbiguousResourceError):
        Resolver().resolve(adapter.load(dcat_config()))
    found = adapter.search(SearchQuery(text="river", limit=1))
    assert len(found) == 1
    assert len(adapter.load(found[0].to_config()).candidates) == 2
    assert adapter.search(SearchQuery(text="absent")) == ()
    assert len(adapter.search(SearchQuery())) == 1


@pytest.mark.parametrize("serialization", ["xml", "json-ld"])
def test_dcat_serializations_have_equivalent_candidates(serialization: str) -> None:
    rdf: Any = importlib.import_module("rdflib")
    graph = rdf.Graph().parse(
        data=(FIXTURES / "catalog.ttl").read_text(), format="turtle"
    )
    document = graph.serialize(format=serialization)
    result = dcat_adapter(document).load(dcat_config(serialization=serialization))
    assert result.candidates == dcat_adapter().load(dcat_config()).candidates


def test_dcat_optional_labels_formats_and_blank_nodes() -> None:
    text = """@prefix dcat: <http://www.w3.org/ns/dcat#> .
    [] a dcat:Dataset .
    <https://fixture.example/dataset> a dcat:Dataset ; dcat:distribution [
        dcat:downloadURL <https://fixture.example/file> ] ."""
    adapter = dcat_adapter(text)
    assert len(adapter.search(SearchQuery())) == 1
    result = adapter.load(dcat_config())
    assert result.metadata.title == "https://fixture.example/dataset"
    with pytest.raises(UnsupportedAccessError):
        Resolver().resolve(result)


def test_dcat_distinguishes_bad_config_fetch_parse_and_missing_dataset() -> None:
    with pytest.raises(ConfigValidationError):
        dcat_adapter().load(dcat_config(serialization="csv"))
    with pytest.raises(ProviderMetadataError):
        DcatAdapter(fail, lambda: None).load(dcat_config())
    with pytest.raises(ProviderResponseError):
        dcat_adapter("not valid turtle (").load(dcat_config())
    with pytest.raises(ResourceNotFoundError):
        dcat_adapter().load(dcat_config(dataset="https://absent.example"))


@pytest.mark.parametrize("adapter", [dcat_adapter()])
def test_local_search_rejects_unsupported_conditions(adapter: Any) -> None:
    with pytest.raises(UnsupportedSearchConditionError):
        adapter.search(SearchQuery(bbox=(0, 0, 1, 1)))
    for limit in (-1, True):
        with pytest.raises(ConfigValidationError):
            adapter.search(SearchQuery(limit=limit))
    assert adapter.search(SearchQuery(limit=0)) == ()


@pytest.mark.parametrize(
    "adapter",
    [
        GsiFundamentalAdapter(),
        dcat_adapter(),
        odpt_adapter(),
    ],
)
def test_expansion_adapters_reject_wrong_source_type(adapter: Any) -> None:
    with pytest.raises(ConfigValidationError):
        adapter.load(Config("wrong", {}))


@pytest.mark.parametrize(
    "settings",
    [
        {"dataset": "bus", "credential": "odpt"},
        {"dataset": "station", "credential": ""},
        {"dataset": "station", "credential": "odpt", "token": "secret"},
        {"dataset": "station", "credential": "odpt", "filters": []},
        {"dataset": "station", "credential": "odpt", "filters": {"unknown": "x"}},
        {"dataset": "station", "credential": "odpt", "filters": {"dc:title": ""}},
    ],
)
def test_odpt_rejects_unknown_or_secret_settings(settings: Mapping[str, Any]) -> None:
    with pytest.raises(ConfigValidationError):
        odpt_adapter().load(Config("odpt", settings))


def test_odpt_catalog_shapes_are_rejected() -> None:
    changes = (
        {"endpoint": None},
        {"endpoint": ""},
        {"resource_types": None},
        {"resource_types": {}},
        {"resource_types": {1: "odpt:Station"}},
        {"resource_types": {"station": 1}},
        {"resource_types": {"station": ""}},
        {
            "resource_types": {
                "station": "odpt:Station",
                "railway": "odpt:Railway",
            }
        },
        {"filter_fields": None},
        {"filter_fields": {}},
        {"filter_fields": {1: []}},
        {"filter_fields": {"station": "dc:title"}},
        {"filter_fields": {"station": [1]}},
        {"spec_source": None},
        {"terms_url": ""},
    )
    for change in changes:
        kwargs = dict(sources.ODPT.settings)
        kwargs.update(cast(Mapping[str, Any], change))
        with pytest.raises(ConfigValidationError):
            OdptAdapter(**kwargs)


def test_odpt_runtime_filters_are_validated() -> None:
    adapter = odpt_adapter()
    adapter.config_schema = lambda: None  # type: ignore[method-assign]
    with pytest.raises(ConfigValidationError, match="filters"):
        adapter.load(
            Config(
                "odpt",
                {
                    "dataset": "station",
                    "credential": "odpt",
                    "filters": [],
                },
            )
        )


def test_odpt_credentials_are_lazy_isolated_and_not_stored_in_resource() -> None:
    calls: Dict[str, Any] = {}
    data = json.loads((FIXTURES / "odpt.json").read_text())

    def get(uri: str, **kwargs: Any) -> Any:
        calls.update(kwargs)
        calls["uri"] = uri
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None, json=lambda: data
        )

    factory_calls: List[bool] = []

    def credential() -> str:
        factory_calls.append(True)
        return "rotating-secret"

    app = configure(
        sources=(sources.ODPT,),
        dependencies={"json-service": lambda: SimpleNamespace(get=get)},
        credentials={"odpt": credential},
    )
    config = Config(
        "odpt",
        {"dataset": "station", "credential": "odpt", "filters": {"dc:title": "東京"}},
    )
    resource = app.resolve(config)
    assert not factory_calls
    assert resource.access_plan.kind == "service-query"
    assert resource.open() == data
    assert calls["params"] == {"dc:title": "東京", "acl:consumerKey": "rotating-secret"}
    assert calls["allow_redirects"] is False
    assert "rotating-secret" not in repr(resource)
    assert resource.open() == data
    assert len(factory_calls) == 2
    other = configure(
        sources=(sources.ODPT,),
        dependencies={"json-service": lambda: SimpleNamespace(get=get)},
    )
    with pytest.raises(CredentialUnavailableError):
        other.open(config)
    for dataset in ("railway", "train"):
        assert (
            odpt_adapter()
            .load(Config("odpt", {"dataset": dataset, "credential": "odpt"}))
            .candidates
        )


def test_credential_errors_do_not_expose_factory_secrets() -> None:
    for factory in (fail, lambda: "", lambda: cast(Any, 123)):
        with pytest.raises(CredentialLoadError) as error:
            CredentialRegistry({"key": factory}).get("key")
        assert "secret-in-underlying-error" not in str(error.value)
        assert error.value.__context__ is None or error.value.__suppress_context__


def test_odpt_rejects_incomplete_service_plan() -> None:
    endpoint = "https://api.odpt.org/api/v4/odpt:Station"
    plan = ServiceQueryPlan(
        uri=endpoint,
        options={
            "service": "odpt",
            "endpoint": endpoint,
        },
    )
    with pytest.raises(ConfigValidationError, match="incomplete"):
        OdptAdapter.prepare_request(plan, CredentialRegistry({}))


def test_odpt_authentication_cannot_be_redirected_to_another_provider() -> None:
    plan = ServiceQueryPlan(uri="https://evil.example", options={"service": "odpt"})
    with pytest.raises(ConfigValidationError):
        OdptAdapter.prepare_request(
            plan, CredentialRegistry({"odpt": lambda: "secret"})
        )


@pytest.mark.parametrize(
    "response,expected",
    [
        (SimpleNamespace(status_code=302), ResourceAccessError),
        (SimpleNamespace(status_code=401, raise_for_status=fail), ResourceAccessError),
        (
            SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=fail),
            ProviderResponseError,
        ),
        (
            SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: cast(Mapping[str, Any], {}),
            ),
            ProviderResponseError,
        ),
        (
            SimpleNamespace(
                status_code=200, raise_for_status=lambda: None, json=lambda: [1]
            ),
            ProviderResponseError,
        ),
    ],
)
def test_json_service_errors_are_distinct_and_redacted(
    response: Any, expected: Any
) -> None:
    item = odpt_adapter().load(
        Config("odpt", {"dataset": "station", "credential": "odpt"})
    )
    execution = JsonServiceAdapter(
        OdptAdapter.prepare_request,
        "odpt",
        CredentialRegistry({"odpt": lambda: "secret"}),
    )

    def get(url: str, **kwargs: Any) -> Any:
        return response

    with pytest.raises(expected) as error:
        execution.open(
            Resolver().resolve(item),
            SimpleNamespace(get=get),
        )
    assert "secret-in-underlying-error" not in str(error.value)


def test_json_service_is_not_odpt_specific() -> None:
    item = make_source(
        ResourceCandidate(
            "https://fixture.example",
            "api",
            "application/json",
            {"access_kind": "service-query", "access_options": {"service": "custom"}},
        )
    )
    resource = Resolver().resolve(item)
    adapter = JsonServiceAdapter(
        lambda plan, credentials: (
            cast(Mapping[str, Any], {}),
            cast(Mapping[str, str], {}),
        ),
        "custom",
    )
    assert adapter.supports(resource, frozenset({"json-service"}))
    response = SimpleNamespace(
        status_code=200, raise_for_status=lambda: None, json=lambda: {"ok": True}
    )

    def get(url: str, **kwargs: Any) -> Any:
        return response

    assert adapter.open(resource, SimpleNamespace(get=get)) == {"ok": True}


@pytest.mark.parametrize(
    "attributes,error",
    [
        ({"matches_config": False}, ResourceNotFoundError),
        ({"matches_config": "yes"}, UnsupportedAccessError),
        ({"access_kind": 1}, UnsupportedAccessError),
        ({"access_kind": "file", "access_options": []}, UnsupportedAccessError),
    ],
)
def test_resolver_validates_explicit_candidate_contract(
    attributes: Mapping[str, Any], error: Any
) -> None:
    with pytest.raises(error):
        Resolver().resolve(
            make_source(ResourceCandidate("file", "gml", None, attributes))
        )


def test_gdal_null_result_is_an_access_failure() -> None:
    resource = Resolver().resolve(make_source(ResourceCandidate("file", "gml", None)))

    def open_ex(uri: str, **kwargs: Any) -> None:
        return None

    with pytest.raises(ResourceAccessError):
        GdalAdapter().open(resource, SimpleNamespace(OpenEx=open_ex))


def test_execution_uses_selected_candidate_attributes_when_uri_is_shared() -> None:
    from rhinestone.adapters.execution import resource_attributes

    rejected = ResourceCandidate("same", "gml", None, {"matches_config": False})
    selected = replace(
        rejected, attributes={"matches_config": True, "encoding": "utf8"}
    )
    resource = Resolver().resolve(make_source(rejected, selected))
    assert resource_attributes(resource)["encoding"] == "utf8"
