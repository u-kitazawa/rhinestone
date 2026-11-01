from collections.abc import Mapping

import pytest

from rhinestone.errors import ConfigValidationError, UnsupportedAccessError
from rhinestone.models import Metadata, Provenance, Reference
from rhinestone.resolution import resource_from_delivery


def delivery(
    format_name: str | None,
    *,
    media_type: str | None = "application/octet-stream",
    kind: str | None = None,
    options: Mapping[str, object] | None = None,
    archive: str | None = None,
):
    return resource_from_delivery(
        reference=Reference("fixture", "dataset", "delivery"),
        uri="https://example.jp/resource",
        format=format_name,
        media_type=media_type,
        metadata=Metadata(title="Dataset"),
        provenance=Provenance(provider="fixture"),
        kind=kind,
        options=options,
        archive=archive,
    )


def test_unknown_format_remains_explicitly_unresolved_without_suffix_guessing() -> None:
    resource = resource_from_delivery(
        reference=Reference("fixture", "dataset", "delivery"),
        uri="https://example.jp/looks-like.csv",
        format=None,
        media_type=None,
        metadata=Metadata(title="Dataset"),
        provenance=Provenance(provider="fixture"),
    )

    assert resource.format is None
    assert resource.access_plan is None


@pytest.mark.parametrize(
    ("format_name", "expected_kind"),
    (
        ("cog", "remote-dataset"),
        ("wms", "service-query"),
        ("ogc-api-features", "service-query"),
        ("csv", "file"),
    ),
)
def test_known_delivery_shapes_create_explicit_access_plans(
    format_name: str, expected_kind: str
) -> None:
    resource = delivery(format_name)

    assert resource.access_plan is not None
    assert resource.access_plan.kind == expected_kind


def test_removed_estat_format_is_a_file_delivery() -> None:
    resource = delivery("estat-api", media_type="application/json")

    assert resource.access_plan is not None
    assert resource.access_plan.kind == "file"


def test_delivery_consumes_shared_canonical_format_vocabulary() -> None:
    resource = delivery("GeoPackage")

    assert resource.format == "gpkg"
    assert resource.access_plan is not None
    assert resource.access_plan.kind == "file"


def test_archive_knowledge_is_preserved_in_file_plan() -> None:
    resource = delivery("zip", media_type="application/zip")

    assert resource.access_plan is not None
    assert resource.access_plan.options["archive"] == "zip"


@pytest.mark.parametrize("kind", ("file", "service-query"))
def test_provider_can_declare_each_supported_plan_kind(kind: str) -> None:
    resource = delivery("custom", kind=kind)

    assert resource.access_plan is not None
    assert resource.access_plan.kind == kind


def test_unknown_custom_plan_kind_fails_explicitly() -> None:
    with pytest.raises(ConfigValidationError, match="kind"):
        delivery("custom", kind="mystery")


@pytest.mark.parametrize(
    ("options", "archive"),
    (
        ({}, "tar"),
        ({"entry_point": "../outside.gml"}, "zip"),
        ({"entry_point": "dir\\file.gml"}, "zip"),
        ({"entry_point": "."}, "zip"),
        ({"entry_point": "file.gml"}, None),
    ),
)
def test_file_plan_rejects_unsupported_or_unsafe_archive_metadata(
    options: Mapping[str, object], archive: str | None
) -> None:
    with pytest.raises(UnsupportedAccessError, match="archive|entry_point"):
        delivery("gml", options=options, archive=archive)
