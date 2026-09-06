from typing import Mapping

import pytest

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


def test_catalog_resource_rejects_path_traversal() -> None:
    with pytest.raises(ConfigValidationError):
        load_catalog_resource("../sources.json")
