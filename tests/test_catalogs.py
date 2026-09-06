from typing import Any, Mapping

import pytest

import rhinestone.catalogs as catalog_module
from rhinestone import SourceDefinition, sources
from rhinestone.catalogs import load_catalog_resource, load_source_definitions
from rhinestone.errors import ConfigValidationError


def test_builtin_sources_are_loaded_from_the_repository_catalog() -> None:
    definitions = load_source_definitions()

    assert tuple(definition.id for definition in definitions) == (
        "geospatial-jp",
        "estat",
        "plateau",
        "gsi",
        "odpt",
    )
    assert definitions == sources.ALL
    assert all(isinstance(definition, SourceDefinition) for definition in sources.ALL)


def test_catalog_contains_service_configuration_but_not_runtime_values() -> None:
    assert sources.GEOSPATIAL_JP.settings["endpoint"] == (
        "https://www.geospatial.jp/ckan"
    )
    assert sources.ESTAT.settings["endpoint"] == (
        "https://api.e-stat.go.jp/rest/3.0/app/json"
    )
    assert sources.ODPT.settings["endpoint"] == "https://api.odpt.org/api/v4"
    for source in sources.ALL:
        assert "credentials" not in source.settings
        assert "dependencies" not in source.settings
        assert "api_key" not in source.settings
        assert "api_token" not in source.settings


def test_tile_adapter_catalog_is_loaded_independently_from_the_adapter() -> None:
    specs = load_catalog_resource("gsi_tile_specs.json")

    assert isinstance(specs, Mapping)
    assert "std" in specs
    standard = specs["std"]
    assert isinstance(standard, Mapping)
    assert standard["url"].startswith("https://")
    assert standard["scheme"] == "xyz"
    assert standard["format"] == "png"


@pytest.mark.parametrize("name", (None, "", "../sources.json", "a\\b", ".", ".."))
def test_catalog_resource_rejects_invalid_names(name: Any) -> None:
    with pytest.raises(ConfigValidationError):
        load_catalog_resource(name)


def test_catalog_resource_errors_are_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(
        catalog_module.resources,
        "files",
        lambda package: FakePackage(),
    )
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
        {"sources": {"broken": {"adapter_type": None}}},
        {"sources": {"broken": {"adapter_type": ""}}},
        {"sources": {"broken": {"adapter_type": "static", "settings": []}}},
    ),
)
def test_source_catalog_manifest_shapes_are_rejected(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        catalog_module,
        "load_catalog_resource",
        lambda name: document,
    )
    with pytest.raises(ConfigValidationError):
        load_source_definitions("fixture.json")


def test_source_catalog_item_resource_shapes_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = (
        {
            "sources": {
                "gsi": {
                    "adapter_type": "static",
                    "settings": {"items": {}, "items_resource": "items.json"},
                }
            }
        },
        {
            "sources": {
                "gsi": {
                    "adapter_type": "static",
                    "settings": {"items_resource": 0},
                }
            }
        },
        {
            "sources": {
                "gsi": {
                    "adapter_type": "static",
                    "settings": {"items_resource": ""},
                }
            }
        },
        {
            "sources": {
                "gsi": {
                    "adapter_type": "static",
                    "settings": {"items_resource": "items.json"},
                }
            }
        },
    )
    for document in documents:
        monkeypatch.setattr(
            catalog_module,
            "load_catalog_resource",
            lambda name, document=document: (
                [] if name == "items.json" else document
            ),
        )
        with pytest.raises(ConfigValidationError):
            load_source_definitions("fixture.json")
