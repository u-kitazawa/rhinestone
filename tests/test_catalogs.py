from collections.abc import Mapping, Sequence
from typing import Any, cast

import pytest

import rhinestone.catalogs as catalog_module
from rhinestone import Provider
from rhinestone.catalogs import (
    BUILTIN,
    Catalog,
    load_catalog_resource,
    load_source_catalog,
    load_source_definitions,
)
from rhinestone.errors import ConfigValidationError


def test_builtin_sources_are_loaded_from_the_repository_catalog() -> None:
    definitions = load_source_definitions()

    assert tuple(definition.id for definition in definitions) == (
        "geospatial-jp",
        "plateau",
        "gsi",
        "odpt",
        "mlit-dpf",
        "search-ckan-jp",
    )
    catalog_entries = load_source_catalog()
    assert tuple(entry.provider for entry in catalog_entries) == definitions
    assert tuple(entry.name for entry in catalog_entries) == (
        "GEOSPATIAL_JP",
        "PLATEAU",
        "GSI",
        "ODPT",
        "MLIT_DPF",
        "SEARCH_CKAN_JP",
    )
    assert definitions == BUILTIN.providers
    assert all(isinstance(definition, Provider) for definition in BUILTIN.providers)


def test_catalog_contains_service_configuration_but_not_runtime_values() -> None:
    assert BUILTIN[0].settings["endpoint"] == ("https://www.geospatial.jp/ckan")
    assert BUILTIN[3].settings["endpoint"] == "https://api.odpt.org/api/v4"
    for source in BUILTIN.providers:
        assert "credentials" not in source.settings
        assert "dependencies" not in source.settings
        assert "api_key" not in source.settings
        assert "api_token" not in source.settings


def test_gsi_tiles_are_defined_in_sources_catalog() -> None:
    assert BUILTIN[2].adapter_type == "static"
    raw_items = BUILTIN[2].settings["items"]
    assert isinstance(raw_items, Mapping)
    items = cast(Mapping[str, Any], raw_items)
    assert set(items) == {"std", "pale"}
    raw_standard = items["std"]
    assert isinstance(raw_standard, Mapping)
    standard = cast(Mapping[str, Any], raw_standard)
    metadata = cast(Mapping[str, Any], standard["metadata"])
    assert metadata["title"] == "標準地図"
    candidates = cast(Sequence[Mapping[str, Any]], standard["candidates"])
    assert candidates[0]["uri"].endswith("/std/{z}/{x}/{y}.png")


@pytest.mark.parametrize("name", (None, "", "../sources.json", "a\\b", ".", ".."))
def test_catalog_resource_rejects_invalid_names(name: Any) -> None:
    with pytest.raises(ConfigValidationError):
        load_catalog_resource(name)


def test_catalog_resource_errors_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResource:
        def __init__(self, text: str) -> None:
            self.text = text

        def read_text(self, encoding: str) -> str:
            if self.text == "missing":
                raise FileNotFoundError
            return self.text

    class FakePackage:
        def joinpath(self, name: str) -> FakeResource:
            return FakeResource("missing" if name == "missing.json" else "{")

    def fake_files(package: Any) -> FakePackage:
        return FakePackage()

    monkeypatch.setattr(catalog_module.resources, "files", fake_files)
    with pytest.raises(ConfigValidationError, match="not found"):
        load_catalog_resource("missing.json")
    with pytest.raises(ConfigValidationError, match="invalid JSON"):
        load_catalog_resource("invalid.json")


@pytest.mark.parametrize(
    "document",
    (
        [],
        {"sources": None},
        {"sources": {}},
        {"sources": {1: {}}},
        {"sources": {"broken": []}},
        {"sources": {"broken": {}}},
        {"sources": {"broken": {"name": "BROKEN", "adapter_type": None}}},
        {"sources": {"broken": {"name": "BROKEN", "adapter_type": ""}}},
        {
            "sources": {
                "broken": {
                    "name": "BROKEN",
                    "adapter_type": "static",
                    "settings": [],
                }
            }
        },
        {"sources": {"broken": {"adapter_type": "static"}}},
        {"sources": {"broken": {"name": None, "adapter_type": "static"}}},
        {"sources": {"broken": {"name": "", "adapter_type": "static"}}},
        {
            "sources": {
                "first": {"name": "DUPLICATE", "adapter_type": "static"},
                "second": {"name": "DUPLICATE", "adapter_type": "static"},
            }
        },
    ),
)
def test_source_catalog_manifest_shapes_are_rejected(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_load_catalog_resource(name: str) -> Any:
        return document

    monkeypatch.setattr(
        catalog_module, "load_catalog_resource", fake_load_catalog_resource
    )
    with pytest.raises(ConfigValidationError):
        load_source_definitions("fixture.json")


def test_catalog_is_an_immutable_provider_collection() -> None:
    catalog = Catalog((BUILTIN[2],))
    extended = catalog.add(BUILTIN[3])

    assert len(catalog) == 1
    assert catalog[0] is BUILTIN[2]
    assert load_source_catalog()[0].provider == BUILTIN[0]
    assert tuple(catalog) == (BUILTIN[2],)
    assert extended.providers == (BUILTIN[2], BUILTIN[3])
    assert tuple(extended) == (BUILTIN[2], BUILTIN[3])
