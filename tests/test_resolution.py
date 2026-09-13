from typing import Mapping, Tuple, cast

import pytest

from rhinestone.errors import AmbiguousResourceError, UnsupportedAccessError
from rhinestone.models import (
    FileAccessPlan,
    Metadata,
    Provenance,
    ResourceCandidate,
    Source,
)
from rhinestone.resolution import Resolver


def make_source(*candidates: ResourceCandidate) -> Source:
    return Source(
        metadata=Metadata(title="Dataset", raw={}),
        candidates=candidates,
        capabilities=frozenset({"download"}),
        provenance=Provenance(provider="fixture", raw={}),
        raw_metadata={},
    )


def test_resolution_is_independent_of_rule_registration_order() -> None:
    """同じ入力から同じ AccessPlan を得る決定性を登録順に左右されないよう保証する。"""
    candidate = ResourceCandidate(
        uri="https://example.jp/data.tif",
        format="cog",
        media_type="image/tiff",
    )

    def lower_priority(item: ResourceCandidate) -> Tuple[int, str]:
        return (10, "file")

    def higher_priority(item: ResourceCandidate) -> Tuple[int, str]:
        return (20, "remote-dataset")

    forward = Resolver(rules=(lower_priority, higher_priority)).resolve(
        make_source(candidate)
    )
    reverse = Resolver(rules=(higher_priority, lower_priority)).resolve(
        make_source(candidate)
    )

    assert forward == reverse
    assert forward.access_plan.kind == "remote-dataset"


def test_ambiguous_resource_selection_fails_explicitly() -> None:
    """複数候補から URI を推測する silent fallback を防ぐために必要である。"""
    candidates = (
        ResourceCandidate("https://example.jp/a.csv", "csv", "text/csv"),
        ResourceCandidate("https://example.jp/b.csv", "csv", "text/csv"),
    )

    with pytest.raises(AmbiguousResourceError):
        Resolver().resolve(make_source(*candidates))


def test_unknown_format_fails_instead_of_guessing_from_url_suffix() -> None:
    """URL suffix から未提示 format を補完する推測を禁止するために必要である。"""
    candidate = ResourceCandidate(
        uri="https://example.jp/looks-like.csv",
        format=None,
        media_type=None,
    )

    with pytest.raises(UnsupportedAccessError):
        Resolver().resolve(make_source(candidate))


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
    """File・remote dataset・service query の配信差を明示モデルで保持するために必要である。"""
    candidate = ResourceCandidate(
        "https://example.jp/resource", format_name, "application/octet-stream"
    )

    resource = Resolver().resolve(make_source(candidate))

    assert resource.access_plan.kind == expected_kind


def test_removed_estat_format_is_not_a_builtin_service_format() -> None:
    """削除したe-Stat統計表API形式を汎用service-queryとして扱わない。"""
    candidate = ResourceCandidate(
        "https://example.jp/resource", "estat-api", "application/json"
    )

    resource = Resolver().resolve(make_source(candidate))

    assert resource.access_plan.kind == "file"


def test_resolution_consumes_shared_canonical_format_vocabulary() -> None:
    candidate = ResourceCandidate(
        "https://example.jp/resource", "GeoPackage", "application/octet-stream"
    )

    resource = Resolver().resolve(make_source(candidate))

    assert resource.format == "gpkg"
    assert resource.access_plan.kind == "file"


def test_archive_knowledge_is_preserved_in_file_plan() -> None:
    """ZIP Resource の archive 情報を Execution Adapter の翻訳へ渡すために必要である。"""
    candidate = ResourceCandidate(
        "https://example.jp/data.zip", "zip", "application/zip"
    )

    resource = Resolver().resolve(make_source(candidate))

    assert cast(FileAccessPlan, resource.access_plan).archive == "zip"


@pytest.mark.parametrize("kind", ("file", "service-query"))
def test_custom_resolution_rules_support_each_declared_plan(kind: str) -> None:
    """Provider 知識を Core の分岐追加なしで明示 AccessPlan に変換するために必要である。"""
    candidate = ResourceCandidate(
        "https://example.jp/resource", "custom", "application/custom"
    )

    resource = Resolver(rules=(lambda item: None, lambda item: (100, kind))).resolve(
        make_source(candidate)
    )

    assert resource.access_plan.kind == kind


def test_unknown_custom_plan_kind_fails_explicitly() -> None:
    """Adapter rule の未知 access method を推測して実行しないために必要である。"""
    candidate = ResourceCandidate(
        "https://example.jp/resource", "custom", "application/custom"
    )

    with pytest.raises(UnsupportedAccessError, match="mystery"):
        Resolver(rules=(lambda item: (100, "mystery"),)).resolve(make_source(candidate))


def test_media_type_alone_does_not_trigger_format_guessing() -> None:
    """明示 format がない Resource を media type だけで暗黙変換しないために必要である。"""
    candidate = ResourceCandidate(
        "https://example.jp/resource", None, "application/octet-stream"
    )

    with pytest.raises(UnsupportedAccessError):
        Resolver().resolve(make_source(candidate))


@pytest.mark.parametrize(
    "attributes",
    (
        {"archive": "tar"},
        {"archive": "zip", "access_options": {"entry_point": "../outside.gml"}},
        {"archive": "zip", "access_options": {"entry_point": "dir\\file.gml"}},
        {"archive": "zip", "access_options": {"entry_point": "."}},
        {"access_options": {"entry_point": "file.gml"}},
    ),
)
def test_file_plan_rejects_unsupported_or_unsafe_archive_metadata(
    attributes: Mapping[str, object],
) -> None:
    candidate = ResourceCandidate(
        "https://example.jp/resource", "gml", None, attributes
    )

    with pytest.raises(UnsupportedAccessError, match="archive|entry_point"):
        Resolver().resolve(make_source(candidate))
