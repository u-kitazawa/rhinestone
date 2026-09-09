from typing import List, Tuple

from rhinestone.models import SearchQuery
from rhinestone.search import SearchCoordinator


class SearchableAdapter:
    source_id = "searchable"
    search_conditions = frozenset({"text", "limit"})

    def __init__(self) -> None:
        self.queries: List[SearchQuery] = []

    def search(self, query: SearchQuery) -> Tuple[object, ...]:
        self.queries.append(query)
        return (object(),)


class ResolveOnlyAdapter:
    source_id = "resolve-only"

    def __init__(self) -> None:
        self.called = False

    def resolve(self, config: object) -> object:
        self.called = True
        return object()


class OrderedSearchableAdapter(SearchableAdapter):
    def __init__(self, source_id: str, results: Tuple[object, ...]) -> None:
        super().__init__()
        self.source_id = source_id
        self.results = results

    def search(self, query: SearchQuery) -> Tuple[object, ...]:
        self.queries.append(query)
        return self.results


def test_search_calls_only_adapters_declaring_search_capability() -> None:
    """検索不能な Source Adapter を federated search が誤って呼ばないために必要である。"""
    searchable = SearchableAdapter()
    resolve_only = ResolveOnlyAdapter()
    coordinator = SearchCoordinator((resolve_only, searchable))
    query = SearchQuery(text="river", limit=5)

    grouped = coordinator.search(query)

    assert searchable.queries == [query]
    assert resolve_only.called is False
    assert tuple(grouped.keys()) == ("searchable",)


def test_unsupported_search_condition_is_reported_and_projected() -> None:
    """非対応条件を診断可能にし、対応条件だけをproviderへ渡すために必要である。"""
    searchable = SearchableAdapter()
    coordinator = SearchCoordinator((searchable,))
    query = SearchQuery(text="river", bbox=(139.0, 35.0, 140.0, 36.0))

    results = coordinator.search(query)

    assert results.diagnostics[0].source_id == "searchable"
    assert results.diagnostics[0].skipped_conditions == frozenset({"bbox"})
    assert searchable.queries == [SearchQuery(text="river")]


def test_results_remain_grouped_by_provider() -> None:
    """比較不能な provider 固有 ranking score を一つの順位へ混ぜないために必要である。"""
    first = SearchableAdapter()
    first.source_id = "stac"
    second = SearchableAdapter()
    second.source_id = "ckan"

    grouped = SearchCoordinator((first, second)).search(SearchQuery(text="river"))

    assert tuple(grouped.keys()) == ("stac", "ckan")
    assert len(grouped["ckan"]) == 1
    assert len(grouped["stac"]) == 1


def test_federated_sequence_uses_configuration_order_not_source_id_order() -> None:
    """Provider名の辞書順を横断rankingの代理にしないために必要である。"""
    first_results = (object(), object())
    second_results = (object(), object())
    first = OrderedSearchableAdapter("z-provider", first_results)
    second = OrderedSearchableAdapter("a-provider", second_results)

    results = SearchCoordinator((first, second)).search(SearchQuery(text="river"))

    assert results.keys() == ("z-provider", "a-provider")
    assert tuple(results) == first_results + second_results
    assert results[0] is first_results[0]
    assert results["z-provider"] == first_results
    assert results["a-provider"] == second_results


def test_single_provider_sequence_preserves_provider_order() -> None:
    """単一Providerで従来のindexing UXとprovider内順序を維持するために必要である。"""
    provider_results = (object(), object())
    provider = OrderedSearchableAdapter("provider", provider_results)

    results = SearchCoordinator((provider,)).search(SearchQuery(text="river"))

    assert tuple(results) == provider_results
    assert results[0] is provider_results[0]
