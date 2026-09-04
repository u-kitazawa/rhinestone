from typing import List, Tuple

import pytest

from rhinestone.errors import UnsupportedSearchConditionError
from rhinestone.models import SearchQuery
from rhinestone.search import SearchCoordinator


class SearchableAdapter:
    source_type = "searchable"
    search_conditions = frozenset({"text", "limit"})

    def __init__(self) -> None:
        self.queries: List[SearchQuery] = []

    def search(self, query: SearchQuery) -> Tuple[object, ...]:
        self.queries.append(query)
        return (object(),)


class ResolveOnlyAdapter:
    source_type = "resolve-only"

    def __init__(self) -> None:
        self.called = False

    def resolve(self, config: object) -> object:
        self.called = True
        return object()


def test_search_calls_only_adapters_declaring_search_capability() -> None:
    """検索不能な Source Adapter を federated search が誤って呼ばないために必要である。"""
    searchable = SearchableAdapter()
    resolve_only = ResolveOnlyAdapter()
    coordinator = SearchCoordinator((resolve_only, searchable))
    query = SearchQuery(text="river", limit=5)

    grouped = coordinator.search(query)

    assert searchable.queries == [query]
    assert resolve_only.called is False
    assert tuple(grouped) == ("searchable",)


def test_unsupported_search_condition_is_not_silently_ignored() -> None:
    """Provider が扱えない bbox 条件で誤った検索結果を返さないために必要である。"""
    coordinator = SearchCoordinator((SearchableAdapter(),))
    query = SearchQuery(text="river", bbox=(139.0, 35.0, 140.0, 36.0))

    with pytest.raises(UnsupportedSearchConditionError, match="bbox"):
        coordinator.search(query)


def test_results_remain_grouped_by_provider() -> None:
    """比較不能な provider 固有 ranking score を一つの順位へ混ぜないために必要である。"""
    first = SearchableAdapter()
    first.source_type = "ckan"
    second = SearchableAdapter()
    second.source_type = "stac"

    grouped = SearchCoordinator((second, first)).search(SearchQuery(text="river"))

    assert tuple(grouped) == ("ckan", "stac")
    assert len(grouped["ckan"]) == 1
    assert len(grouped["stac"]) == 1
