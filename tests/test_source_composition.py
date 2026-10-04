import gc
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from weakref import ref

import pytest
import rdflib

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import (
    Config,
    configure,
)
from rhinestone.catalogs import BUILTIN, Catalog
from rhinestone.errors import (
    ConfigValidationError,
    DependencyUnavailableError,
    ProviderMetadataError,
)
from rhinestone.models import Provider, RuntimeFactory
from tests.provider_support import fixture_json


@pytest.mark.parametrize(
    "source",
    (
        Provider("stac-source", "stac", {"endpoint": "https://stac.test"}),
        Provider(
            "ogc-source",
            "ogc-features",
            {"endpoint": "https://ogc.test", "collection_id": "rivers"},
        ),
        Provider("plateau-source", "plateau", BUILTIN[1].settings),
        Provider("fundamental-source", "gsi-fundamental"),
        Provider("dcat-source", "dcat"),
        Provider("odpt-source", "odpt", BUILTIN[3].settings),
    ),
)
def test_advanced_source_definitions_compose(source: Provider) -> None:
    configure(catalog=Catalog((source,)))


def test_builtin_ckan_and_plateau_searches_have_distinct_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def get_json(url: str, params: Mapping[str, Any]) -> dict[str, Any]:
        assert url.endswith("/api/3/action/package_search")
        calls.append(dict(params))
        packages = (
            []
            if params.get("fq") == "tags:PLATEAU"
            else [
                {
                    "id": "general-roads",
                    "title": "道路データ",
                    "resources": [{"id": "roads-csv", "format": "CSV"}],
                }
            ]
        )
        return {
            "success": True,
            "result": {"count": len(packages), "results": packages},
        }

    monkeypatch.setattr(_http, "get_json", get_json)
    app = configure(catalog=Catalog((BUILTIN[0], BUILTIN[1])))

    results = app.search(text="道路", limit=1)

    assert len(results["geospatial-jp"]) == 1
    assert results["plateau"] == ()
    assert {tuple(sorted(call.items())) for call in calls} == {
        (("q", "道路"), ("rows", 1)),
        (("fq", "tags:PLATEAU"), ("q", "道路"), ("rows", 1)),
    }


def test_dcat_dependencies_are_lazy_and_source_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text(encoding="utf-8")

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)
    dependency_calls: list[str] = []
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "catalog",
                    "dcat",
                    {"catalog_uri": "https://fixture.example/catalog"},
                ),
            )
        ),
        dependencies={
            "rdflib": RuntimeFactory(
                lambda: dependency_calls.append("rdflib") or rdflib
            ),
        },
    )
    assert dependency_calls == []
    resource = app.resolve(
        Config(
            "catalog",
            {
                "uri": "https://fixture.example/catalog",
                "dataset": "https://fixture.example/dataset",
                "distribution": "https://fixture.example/geojson",
                "serialization": "turtle",
            },
        )
    )
    assert resource.uri == "https://fixture.example/rivers.geojson"
    assert dependency_calls == ["rdflib"]


def test_configured_dcat_rejects_tampered_catalog_uri_before_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_calls: list[str] = []

    def get_document(uri: str) -> str:
        document_calls.append(uri)
        return "unused"

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "catalog",
                    "dcat",
                    {"catalog_uri": "https://trusted.example/catalog"},
                ),
            )
        ),
        dependencies={"rdflib": rdflib},
    )

    with pytest.raises(ConfigValidationError, match="catalog URI"):
        app.resolve(
            Config(
                "catalog",
                {
                    "uri": "https://unlisted.example/catalog",
                    "dataset": "https://trusted.example/dataset",
                },
            )
        )

    assert document_calls == []


def test_dcat_search_loads_source_runtime_on_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text(encoding="utf-8")

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)
    dependency_calls: list[str] = []
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "catalog",
                    "dcat",
                    {"catalog_uri": "https://fixture.example/catalog"},
                ),
            )
        ),
        dependencies={
            "rdflib": RuntimeFactory(
                lambda: dependency_calls.append("rdflib") or rdflib
            ),
        },
    )

    assert dependency_calls == []
    assert len(app.search(limit=1)) == 1
    assert dependency_calls == ["rdflib"]


def test_dcat_missing_runtime_is_not_reported_as_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_calls: list[str] = []

    def get_document(uri: str) -> str:
        document_calls.append(uri)
        return "unused"

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(catalog=Catalog((Provider("catalog", "dcat"),)))

    with pytest.raises(DependencyUnavailableError, match="rdflib"):
        app.resolve(
            Config(
                "catalog",
                {
                    "uri": "https://fixture.example/catalog",
                    "dataset": "https://fixture.example/dataset",
                },
            )
        )

    assert document_calls == []


def test_resolved_resource_does_not_retain_source_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text(encoding="utf-8")

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)

    class RdfRuntimeFactory:
        def __call__(self) -> Any:
            return rdflib

    factory = RdfRuntimeFactory()
    factory_ref = ref(factory)
    app = configure(
        catalog=Catalog((Provider("catalog", "dcat"),)),
        dependencies={"rdflib": RuntimeFactory(factory)},
    )
    resource = app.resolve(
        Config(
            "catalog",
            {
                "uri": "https://fixture.example/catalog",
                "dataset": "https://fixture.example/dataset",
                "distribution": "https://fixture.example/geojson",
            },
        )
    )

    del app
    del factory
    gc.collect()

    assert resource.uri == "https://fixture.example/rivers.geojson"
    assert factory_ref() is None


def test_dcat_document_failure_remains_provider_metadata_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_document(uri: str) -> str:
        raise OSError(uri)

    monkeypatch.setattr(_http, "get_text", fail_document)
    app = configure(
        catalog=Catalog((Provider("catalog", "dcat"),)),
        dependencies={"rdflib": rdflib},
    )

    with pytest.raises(ProviderMetadataError, match="RDF catalog"):
        app.resolve(
            Config(
                "catalog",
                {
                    "uri": "https://fixture.example/catalog",
                    "dataset": "https://fixture.example/dataset",
                },
            )
        )


def test_source_options_reject_unknown_values() -> None:
    with pytest.raises(ConfigValidationError, match="typo"):
        configure(
            catalog=Catalog(
                (
                    Provider(
                        "catalog",
                        "ckan",
                        {"endpoint": "https://example.test", "typo": 1},
                    ),
                )
            )
        )


def test_configured_json_transport_supports_adapter_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = "https://catalog.example"
    search_url = endpoint + "/api/3/action/package_search"
    seen: dict[str, Any] = {}

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        seen["headers"] = headers
        return fixture_json("ckan/package_search.json")

    monkeypatch.setattr(_http, "get_json", get_json)
    app = configure(
        catalog=Catalog(
            (
                Provider(
                    "catalog",
                    "ckan",
                    {
                        "endpoint": endpoint,
                        "credential": "test",
                        "credential_header": "X-Test",
                    },
                ),
            )
        ),
        credentials={"test": lambda: "value"},
    )
    app.search(limit=1)
    assert seen["headers"] == {"X-Test": "value"}
    assert search_url
