from typing import Any

import pytest

from rhinestone.adapters.source.ckan import canonical_format as ckan_canonical_format
from rhinestone.representations import (
    CANONICAL_FORMATS,
    CONTAINER_MEDIA_TYPES,
    FORMAT_ALIASES,
    FORMAT_CATEGORIES,
    MEDIA_TYPE_FORMATS,
    canonical_format,
    container_from_media_type,
    format_from_media_type,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (" GeoPackage ", "gpkg"),
        ("GTiff", "geotiff"),
        ("TIFF", "geotiff"),
        ("GeoJSON", "geojson"),
        ("", None),
        ("  ", None),
        (None, None),
        (42, None),
    ),
)
def test_canonical_format_normalizes_known_values_and_rejects_non_strings(
    value: Any, expected: str | None
) -> None:
    assert canonical_format(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("application/geo+json", "geojson"),
        (" APPLICATION/GEOPACKAGE+SQLITE3; charset=utf-8 ", "gpkg"),
        ("image/tiff", "geotiff"),
        ("text/csv; charset=utf-8", "csv"),
        ("application/octet-stream", None),
        ("", None),
        (None, None),
        (42, None),
    ),
)
def test_format_from_media_type_uses_base_media_type(
    value: Any, expected: str | None
) -> None:
    assert format_from_media_type(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("application/zip; charset=binary", "zip"),
        ("application/octet-stream", None),
        ("", None),
        (None, None),
        (42, None),
    ),
)
def test_container_media_type_is_kept_separate_from_payload_format(
    value: Any, expected: str | None
) -> None:
    assert container_from_media_type(value) == expected
    assert format_from_media_type(value) is None


def test_representation_definitions_are_immutable_and_legacy_ckan_import_is_compatible() -> (
    None
):
    assert FORMAT_ALIASES["geopackage"] == "gpkg"
    assert MEDIA_TYPE_FORMATS["image/tiff"] == "geotiff"
    assert CONTAINER_MEDIA_TYPES["application/zip"] == "zip"
    assert "gpkg" in CANONICAL_FORMATS
    assert FORMAT_CATEGORIES["gpkg"] == "vector"
    assert ckan_canonical_format("GeoPackage") == canonical_format("GeoPackage")
    with pytest.raises(TypeError):
        FORMAT_ALIASES["new"] = "format"  # type: ignore[index]
