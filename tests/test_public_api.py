from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import pytest
import rdflib

from rhinestone import Config, ProviderConfig, SearchQuery, configure
from rhinestone.errors import (
    AdapterRegistrationError,
    ConfigValidationError,
    UnsupportedSearchConditionError,
)


class FakeRasterio:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: List[str] = []

    def open(self, uri: str) -> str:
        self.calls.append(uri)
        return self.label + ":" + uri


def direct_config() -> Config:
    return Config(
        "direct",
        {
            "uri": "https://example.test/dataset.tif",
            "format": "geotiff",
            "media_type": "image/tiff",
        },
    )


def test_direct_provider_and_execution_adapters_are_built_in() -> None:
    calls: List[str] = []
    runtime = FakeRasterio("opened")
    app = configure(dependencies={"rasterio": lambda: calls.append("load") or runtime})

    resource = app.resolve(direct_config())

    assert calls == []
    assert resource.open() == "opened:https://example.test/dataset.tif"
    assert calls == ["load"]


def test_resource_open_honours_explicit_built_in_adapter_name() -> None:
    selected: List[str] = []

    class FakeGdal:
        def OpenEx(self, uri: str, **options: object) -> str:
            selected.append("gdal")
            return "gdal-data"

    rasterio = FakeRasterio("rasterio")
    app = configure(
        dependencies={
            "gdal": lambda: FakeGdal(),
            "rasterio": lambda: rasterio,
        }
    )

    resource = app.resolve(direct_config())

    assert resource.open(adapter="rasterio").startswith("rasterio:")
    assert selected == []


def test_two_providers_can_share_one_adapter_type() -> None:
    requests: List[str] = []

    def get_json(
        url: str,
        params: Mapping[str, Any],
        headers: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        requests.append(url)
        catalog = "first" if url.startswith("https://first.test") else "second"
        resource_id = catalog + "-resource"
        if url.endswith("package_search"):
            return {
                "success": True,
                "result": {
                    "results": [
                        {
                            "id": catalog + "-dataset",
                            "title": catalog,
                            "notes": catalog,
                            "resources": [
                                {
                                    "id": resource_id,
                                    "url": f"https://data.test/{resource_id}.geojson",
                                    "format": "geojson",
                                    "mimetype": "application/geo+json",
                                }
                            ],
                        }
                    ]
                },
            }
        if url.endswith("resource_show"):
            return {
                "success": True,
                "result": {
                    "id": resource_id,
                    "package_id": catalog + "-dataset",
                    "url": f"https://data.test/{resource_id}.geojson",
                    "format": "geojson",
                    "mimetype": "application/geo+json",
                },
            }
        return {
            "success": True,
            "result": {
                "id": catalog + "-dataset",
                "title": catalog,
                "notes": catalog,
                "resources": [],
            },
        }

    app = configure(
        providers={
            "catalog-a": ProviderConfig("ckan", {"endpoint": "https://first.test"}),
            "catalog-b": ProviderConfig(
                "ckan",
                {"endpoint": "https://second.test", "api_key": "secret"},
            ),
        },
        dependencies={"http-json": lambda: get_json},
    )

    grouped = app.search(SearchQuery(text="dataset", limit=1))

    assert tuple(grouped) == ("catalog-a", "catalog-b")
    assert grouped["catalog-a"][0].source_id == "catalog-a"
    assert grouped["catalog-b"][0].source_id == "catalog-b"
    first = app.resolve(grouped["catalog-a"][0].to_config())
    assert first.provenance.provider == "catalog-a"
    assert first.provenance.adapter == "ckan"
    assert any(url.startswith("https://first.test") for url in requests)
    assert any(url.startswith("https://second.test") for url in requests)


def test_public_search_exposes_unsupported_conditions_as_domain_error() -> None:
    def unused_get_json(url: str, params: Mapping[str, Any]) -> Dict[str, Any]:
        return {}

    app = configure(
        providers={
            "catalog": ProviderConfig("ckan", {"endpoint": "https://example.test"})
        },
        dependencies={"http-json": lambda: unused_get_json},
    )

    with pytest.raises(UnsupportedSearchConditionError, match="bbox"):
        app.search(SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0)))


def test_configured_contexts_do_not_share_runtime_instances() -> None:
    first_runtime = FakeRasterio("first")
    second_runtime = FakeRasterio("second")
    first = configure(dependencies={"rasterio": lambda: first_runtime})
    second = configure(dependencies={"rasterio": lambda: second_runtime})

    assert first.resolve(direct_config()).open().startswith("first:")
    assert second.resolve(direct_config()).open().startswith("second:")


def test_unknown_built_in_adapter_type_is_rejected() -> None:
    with pytest.raises(AdapterRegistrationError, match="unknown"):
        configure(providers={"custom": ProviderConfig("unknown")})


def test_direct_provider_id_is_reserved() -> None:
    with pytest.raises(AdapterRegistrationError, match="direct"):
        configure(providers={"direct": ProviderConfig("direct")})


def test_empty_provider_id_is_rejected() -> None:
    with pytest.raises(AdapterRegistrationError, match="non-empty"):
        configure(providers={"": ProviderConfig("gsi-tile")})


@pytest.mark.parametrize(
    "provider",
    (
        ProviderConfig("ckan", {"endpoint": "https://example.test"}),
        ProviderConfig("estat", {"app_id": "test"}),
        ProviderConfig("stac", {"endpoint": "https://example.test"}),
        ProviderConfig(
            "ogc-features",
            {"endpoint": "https://example.test", "collection_id": "rivers"},
        ),
        ProviderConfig("plateau"),
        ProviderConfig("gsi-tile"),
        ProviderConfig("gsi-fundamental"),
        ProviderConfig("dcat", {"catalog_uri": "https://example.test/catalog"}),
        ProviderConfig("odpt"),
    ),
)
def test_all_built_in_source_adapter_types_are_composed(
    provider: ProviderConfig,
) -> None:
    configure(providers={"provider": provider})


def test_dcat_source_dependencies_are_lazy_and_provider_scoped() -> None:
    document = (
        Path(__file__).parent / "fixtures" / "expansion" / "catalog.ttl"
    ).read_text()

    def get_document(uri: str) -> str:
        return document

    app = configure(
        providers={"catalog": ProviderConfig("dcat")},
        dependencies={
            "http-text": lambda: get_document,
            "rdflib": lambda: rdflib,
        },
    )

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
    assert resource.provenance.provider == "catalog"


def test_provider_options_reject_typos() -> None:
    with pytest.raises(ConfigValidationError, match="typo"):
        configure(providers={"catalog": ProviderConfig("ckan", {"typo": "value"})})


def test_legacy_adapter_registration_arguments_are_not_public() -> None:
    with pytest.raises(TypeError):
        configure(source_adapters=(), execution_adapters=())  # type: ignore[call-arg]
