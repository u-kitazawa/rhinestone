from typing import Tuple

import pytest

from rhinestone.errors import AmbiguousResourceError, UnsupportedAccessError
from rhinestone.models import Metadata, Provenance, ResourceCandidate, Source
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
