import gc
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from weakref import ref

import pytest
import rdflib

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import (
    Config,
    RuntimeFactory,
    SearchQuery,
    SourceDefinition,
    configure,
    sources,
)
from rhinestone.api import _build_source_adapter  # pyright: ignore[reportPrivateUsage]
from rhinestone.errors import (
    ConfigValidationError,
    DependencyUnavailableError,
    DestinationNotAllowedError,
    ProviderMetadataError,
)
from rhinestone.registry import CredentialRegistry, DependencyRegistry
from tests.provider_support import fixture_json


@pytest.mark.parametrize(
    "source",
    (
        SourceDefinition("stac-source", "stac", {"endpoint": "https://stac.test"}),
        SourceDefinition(
            "ogc-source",
            "ogc-features",
            {"endpoint": "https://ogc.test", "collection_id": "rivers"},
        ),
        SourceDefinition("plateau-source", "plateau", sources.PLATEAU.settings),
        SourceDefinition("fundamental-source", "gsi-fundamental"),
        SourceDefinition("dcat-source", "dcat"),
        SourceDefinition("odpt-source", "odpt", sources.ODPT.settings),
    ),
)
def test_advanced_source_definitions_compose(source: SourceDefinition) -> None:
    configure(sources=(source,))


def test_dcat_dependencies_are_lazy_and_source_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text()

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)
    dependency_calls: List[str] = []
    app = configure(
        sources=(
            SourceDefinition(
                "catalog", "dcat", {"catalog_uri": "https://fixture.example/catalog"}
            ),
        ),
        dependencies={
            "rdflib": RuntimeFactory(
                lambda: dependency_calls.append("rdflib") or rdflib
            ),
        },
        network_policy="strict",
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
    document_calls: List[str] = []

    def get_document(uri: str) -> str:
        document_calls.append(uri)
        return "unused"

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(
        sources=(
            SourceDefinition(
                "catalog",
                "dcat",
                {"catalog_uri": "https://trusted.example/catalog"},
            ),
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


@pytest.mark.parametrize(
    "uri",
    (
        "https://unlisted.example/catalog",
        "file:///tmp/catalog.ttl",
        "/tmp/catalog.ttl",
    ),
)
def test_strict_dcat_rejects_unregistered_catalog_uri_before_fetch(
    monkeypatch: pytest.MonkeyPatch,
    uri: str,
) -> None:
    document_calls: List[str] = []

    def get_document(uri: str) -> str:
        document_calls.append(uri)
        return "unused"

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(
        sources=(SourceDefinition("catalog", "dcat"),),
        network_policy="strict",
    )

    with pytest.raises(DestinationNotAllowedError):
        app.resolve(
            Config(
                "catalog",
                {
                    "uri": uri,
                    "dataset": "https://unlisted.example/dataset",
                },
            )
        )

    assert document_calls == []


def test_dcat_search_loads_source_runtime_on_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text()

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)
    dependency_calls: List[str] = []
    app = configure(
        sources=(
            SourceDefinition(
                "catalog",
                "dcat",
                {"catalog_uri": "https://fixture.example/catalog"},
            ),
        ),
        dependencies={
            "rdflib": RuntimeFactory(
                lambda: dependency_calls.append("rdflib") or rdflib
            ),
        },
        network_policy="strict",
    )

    assert dependency_calls == []
    assert len(app.search(limit=1)) == 1
    assert dependency_calls == ["rdflib"]


def test_dcat_missing_runtime_is_not_reported_as_provider_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_calls: List[str] = []

    def get_document(uri: str) -> str:
        document_calls.append(uri)
        return "unused"

    monkeypatch.setattr(_http, "get_text", get_document)
    app = configure(sources=(SourceDefinition("catalog", "dcat"),))

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
    ).read_text()

    def get_document(uri: str) -> str:
        return document

    monkeypatch.setattr(_http, "get_text", get_document)

    class RdfRuntimeFactory:
        def __call__(self) -> Any:
            return rdflib

    factory = RdfRuntimeFactory()
    factory_ref = ref(factory)
    app = configure(
        sources=(SourceDefinition("catalog", "dcat"),),
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
        sources=(SourceDefinition("catalog", "dcat"),),
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
            sources=(
                SourceDefinition(
                    "catalog", "ckan", {"endpoint": "https://example.test", "typo": 1}
                ),
            )
        )


def test_configured_json_transport_supports_adapter_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = "https://catalog.example"
    search_url = endpoint + "/api/3/action/package_search"
    seen: Dict[str, Any] = {}

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        seen["headers"] = headers
        return fixture_json("ckan/package_search.json")

    monkeypatch.setattr(_http, "get_json", get_json)
    adapter = _build_source_adapter(
        SourceDefinition("catalog", "ckan", {"endpoint": endpoint}),
        DependencyRegistry({}),
        CredentialRegistry({}),
    )
    adapter._headers["X-Test"] = "value"  # type: ignore[attr-defined]
    adapter.search(SearchQuery(limit=1))  # type: ignore[attr-defined]
    assert seen["headers"] == {"X-Test": "value"}
    assert search_url


def test_strict_source_transport_disables_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: List[bool] = []

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
        *,
        allow_redirects: bool = True,
    ) -> Any:
        seen.append(allow_redirects)
        return fixture_json("ckan/package_search.json")

    monkeypatch.setattr(_http, "get_json", get_json)
    app = configure(
        sources=(
            SourceDefinition(
                "catalog", "ckan", {"endpoint": "https://catalog.example"}
            ),
        ),
        network_policy="strict",
    )

    assert app.search(limit=1)
    assert seen == [False]
