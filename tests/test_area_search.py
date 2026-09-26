from typing import Any

import pytest

from rhinestone.adapters.knowledge import (
    AdministrativeArea,
    BoundingBox,
    StaticAdministrativeAreaAdapter,
)
from rhinestone.errors import ConfigValidationError, KnowledgeResolutionError
from rhinestone.models import SearchQuery
from rhinestone.search import SearchCoordinator


AREA = AdministrativeArea(
    canonical_name="神奈川県",
    code="14",
    aliases=("神奈川",),
    bbox=BoundingBox(138.9, 35.1, 139.8, 35.7),
    snapshot_date="2024-01-01",
    source_url="https://example.test/areas",
)


class AreaKnowledge:
    def resolve_area(self, value: str) -> AdministrativeArea:
        return StaticAdministrativeAreaAdapter((AREA,)).resolve_area(value)


class Searchable:
    searchable = True
    required_search_conditions = frozenset()

    def __init__(
        self,
        source_id: str,
        conditions: frozenset[str],
        *,
        text_fallback: bool = False,
    ) -> None:
        self.source_id = source_id
        self.search_conditions = conditions
        self.area_text_fallback = text_fallback
        self.queries: list[SearchQuery] = []

    def search(self, query: SearchQuery) -> tuple[Any, ...]:
        self.queries.append(query)
        return ()


def test_static_area_adapter_resolves_exact_name_alias_and_code() -> None:
    adapter = StaticAdministrativeAreaAdapter((AREA,))

    assert adapter.resolve_area("神奈川県") is AREA
    assert adapter.resolve_area(" 神奈川 ") is AREA
    assert adapter.resolve_area("14") is AREA


def test_static_area_adapter_rejects_unknown_area() -> None:
    with pytest.raises(KnowledgeResolutionError, match="not available"):
        StaticAdministrativeAreaAdapter((AREA,)).resolve_area("未知県")


def test_area_projects_to_bbox_without_changing_bbox_contract() -> None:
    spatial = Searchable("spatial", frozenset({"text", "bbox", "limit"}))

    results = SearchCoordinator((spatial,), AreaKnowledge()).search(
        SearchQuery(text="河川", area="神奈川県", limit=5)
    )

    assert results.diagnostics == ()
    assert spatial.queries == [
        SearchQuery(
            text="河川",
            bbox=(138.9, 35.1, 139.8, 35.7),
            limit=5,
        )
    ]


def test_area_uses_declared_text_fallback_for_non_spatial_source() -> None:
    text = Searchable(
        "text",
        frozenset({"text", "limit"}),
        text_fallback=True,
    )

    SearchCoordinator((text,), AreaKnowledge()).search(
        SearchQuery(text="河川", area="神奈川")
    )

    assert text.queries == [SearchQuery(text="河川 神奈川県")]


def test_area_without_projection_is_reported_and_not_silently_lost() -> None:
    source = Searchable("limit-only", frozenset({"limit"}))

    results = SearchCoordinator((source,), AreaKnowledge()).search(
        SearchQuery(area="神奈川県", limit=1)
    )

    assert source.queries == [SearchQuery(limit=1)]
    assert results.diagnostics[0].source_id == "limit-only"
    assert results.diagnostics[0].reason == "unsupported"
    assert results.diagnostics[0].skipped_conditions == frozenset({"area"})


def test_unknown_area_fails_closed_before_provider_calls() -> None:
    source = Searchable("spatial", frozenset({"bbox"}))

    results = SearchCoordinator((source,), AreaKnowledge()).search(
        SearchQuery(area="未知県")
    )

    assert source.queries == []
    assert results.keys() == ()
    assert results.diagnostics[0].reason == "area_resolution_failed"
    assert results.diagnostics[0].skipped_conditions == frozenset({"area"})


def test_area_and_bbox_cannot_be_supplied_together() -> None:
    with pytest.raises(ConfigValidationError, match="area and bbox"):
        SearchQuery(area="神奈川県", bbox=(139.0, 35.0, 140.0, 36.0))
