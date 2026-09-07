from typing import Any, Dict, List, Mapping, Optional

import pytest

import rhinestone._http as _http  # pyright: ignore[reportPrivateUsage]
from rhinestone import (
    Catalog,
    Config,
    Provider,
    SearchQuery,
    SourceDefinition,
    configure,
    sources,
)
from rhinestone.errors import (
    AdapterRegistrationError,
    UnsupportedSearchConditionError,
    UnsupportedSourceError,
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


def test_direct_and_execution_adapters_are_built_in() -> None:
    calls: List[str] = []
    runtime = FakeRasterio("opened")
    app = configure(dependencies={"rasterio": lambda: calls.append("load") or runtime})

    resource = app.resolve(direct_config())

    assert calls == []
    assert resource.open("rasterio") == "opened:https://example.test/dataset.tif"
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

    assert resource.open("rasterio").startswith("rasterio:")
    assert selected == []


def test_all_is_an_immutable_tuple_of_all_builtin_external_sources() -> None:
    assert isinstance(sources.ALL, tuple)
    assert sources.ALL == (
        sources.GEOSPATIAL_JP,
        sources.ESTAT,
        sources.PLATEAU,
        sources.GSI,
        sources.ODPT,
    )
    assert all(isinstance(source, SourceDefinition) for source in sources.ALL)
    assert all(source.id != "direct" for source in sources.ALL)


def test_source_definitions_do_not_store_runtime_or_secret_values() -> None:
    for source in sources.ALL:
        assert "credentials" not in source.settings
        assert "dependencies" not in source.settings
        assert "app_id" not in source.settings
        assert "api_key" not in source.settings
        assert "api_token" not in source.settings


def test_configure_all_composes_without_loading_dependencies_or_credentials() -> None:
    dependency_calls: List[bool] = []
    credential_calls: List[bool] = []

    configure(
        sources=sources.ALL,
        dependencies={"rasterio": lambda: dependency_calls.append(True)},
        credentials={"estat": lambda: credential_calls.append(True) or "secret"},
    )

    assert dependency_calls == []
    assert credential_calls == []


def test_configure_one_source_only_enables_that_source_and_direct() -> None:
    app = configure(sources=(sources.GSI,))

    assert app.resolve(Config("gsi", {"id": "std"})).provenance.provider == "gsi"
    assert app.resolve(direct_config()).provenance.provider == "direct"
    with pytest.raises(UnsupportedSourceError, match="geospatial-jp"):
        app.resolve(Config("geospatial-jp", {"resource_id": "x"}))


def test_two_sources_can_share_one_adapter_type_without_endpoint_in_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    monkeypatch.setattr(_http, "get_json", get_json)
    first = SourceDefinition("catalog-a", "ckan", {"endpoint": "https://first.test"})
    second = SourceDefinition("catalog-b", "ckan", {"endpoint": "https://second.test"})
    app = configure(sources=(first, second))

    grouped = app.search(SearchQuery(text="dataset", limit=1))

    assert tuple(grouped.keys()) == ("catalog-a", "catalog-b")
    result = grouped["catalog-a"][0]
    assert result.source_id == "catalog-a"
    assert result.settings == {"resource_id": "first-resource"}
    assert "endpoint" not in result.settings
    config = result.to_config()
    assert config == Config("catalog-a", {"resource_id": "first-resource"})
    resolved = app.resolve(config)
    assert resolved.provenance.provider == "catalog-a"
    assert resolved.provenance.adapter == "ckan"
    assert any(url.startswith("https://first.test") for url in requests)
    assert any(url.startswith("https://second.test") for url in requests)
    assert len(grouped) == 2
    assert list(grouped) == [grouped[0], grouped[1]]
    assert grouped[0].source_id == "catalog-a"
    assert tuple(grouped[:1]) == (grouped[0],)
    assert grouped.get("catalog-a") == grouped["catalog-a"]
    assert grouped.get("missing") == ()
    assert tuple(grouped.values())[0] == grouped["catalog-a"]
    assert tuple(grouped.items())[0][0] == "catalog-a"

    simple = app.search("dataset")
    assert simple[0].title == "first"
    assert simple[0].resolve().provenance.provider == "catalog-a"


def test_public_search_exposes_unsupported_conditions_as_domain_error() -> None:
    source = SourceDefinition("catalog", "ckan", {"endpoint": "https://example.test"})
    app = configure(sources=(source,))

    with pytest.raises(UnsupportedSearchConditionError, match="bbox"):
        app.search(SearchQuery(bbox=(139.0, 35.0, 140.0, 36.0)))


def test_duplicate_source_id_is_rejected_during_configuration() -> None:
    with pytest.raises(AdapterRegistrationError, match="registered more than once"):
        configure(sources=(sources.GSI, sources.GSI))


def test_direct_source_id_is_reserved() -> None:
    with pytest.raises(AdapterRegistrationError, match="direct"):
        configure(sources=(SourceDefinition("direct", "static"),))


def test_unknown_built_in_adapter_type_is_rejected() -> None:
    with pytest.raises(AdapterRegistrationError, match="unknown"):
        configure(sources=(SourceDefinition("custom", "unknown"),))


def test_configured_contexts_do_not_share_runtime_instances() -> None:
    first_runtime = FakeRasterio("first")
    second_runtime = FakeRasterio("second")
    first = configure(dependencies={"rasterio": lambda: first_runtime})
    second = configure(dependencies={"rasterio": lambda: second_runtime})

    assert first.resolve(direct_config()).open("rasterio").startswith("first:")
    assert second.resolve(direct_config()).open("rasterio").startswith("second:")


def test_concrete_dependency_object_is_accepted() -> None:
    runtime = FakeRasterio("direct")
    app = configure(dependencies={"rasterio": runtime})

    resource = app.resolve(direct_config())

    assert resource.open("rasterio") == "direct:https://example.test/dataset.tif"


def test_resource_open_requires_a_library_name() -> None:
    app = configure(dependencies={"rasterio": FakeRasterio("runtime")})
    resource = app.resolve(direct_config())

    with pytest.raises(TypeError):
        resource.open()  # type: ignore[call-arg]


def test_legacy_provider_composition_api_is_not_public() -> None:
    with pytest.raises(TypeError):
        configure(providers={})  # type: ignore[call-arg]


def test_catalog_provider_and_result_are_the_short_public_path() -> None:
    catalog = Catalog((sources.GSI,))
    app = configure(catalog=catalog)

    assert isinstance(sources.GSI, Provider)
    assert tuple(catalog) == (sources.GSI,)
    result = app.search(text="標準", limit=1)[0]
    resource = app.resolve(result)

    assert result.title == "標準地図"
    assert resource.provenance.provider == "gsi"


def test_catalog_and_provider_selection_conflicts_are_rejected() -> None:
    with pytest.raises(TypeError, match="either catalog or sources"):
        configure(sources=(sources.GSI,), catalog=Catalog((sources.GSI,)))


def test_search_parameters_and_open_shortcuts_are_supported() -> None:
    app = configure(dependencies={"rasterio": FakeRasterio("runtime")})

    with pytest.raises(TypeError, match="either query or search parameters"):
        app.search("dataset", text="dataset")

    resource = app.resolve(direct_config())
    assert app.open(resource, "rasterio") == "runtime:https://example.test/dataset.tif"
    assert (
        app.open(direct_config(), "rasterio")
        == "runtime:https://example.test/dataset.tif"
    )

    result = Result(
        title="direct",
        description=None,
        source_id="direct",
        settings=direct_config().settings,
        metadata=Metadata(),
        provenance=Provenance(provider="direct"),
    )
    assert app.open(result, "rasterio") == "runtime:https://example.test/dataset.tif"
