from importlib import resources


def test_builtin_catalog_is_available_as_a_package_resource() -> None:
    catalog = resources.files("rhinestone.catalogs").joinpath("gsi_tiles.json")

    assert catalog.is_file()
