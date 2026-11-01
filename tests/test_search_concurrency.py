from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from rhinestone.errors import ProviderResponseError
from rhinestone.models import ProviderSearchResults, SearchDiagnostic, SearchQuery
from rhinestone.search import SearchCoordinator

from .test_search import DiagnosticSearchableAdapter, SearchableAdapter


def test_parallel_search_keeps_results_diagnostics_and_timings_in_catalog_order() -> (
    None
):
    later_finished = Event()
    first_results = (object(), object())

    class First(SearchableAdapter):
        source_id = "first"

        def search(self, query: SearchQuery) -> tuple[object, ...]:
            assert later_finished.wait(5), "second provider never ran concurrently"
            return first_results

    class Second(SearchableAdapter):
        source_id = "second"

        def search(self, query: SearchQuery) -> tuple[object, ...]:
            later_finished.set()
            raise ProviderResponseError("private response")

    class Third(DiagnosticSearchableAdapter):
        source_id = "third"

        def search(self, query: SearchQuery) -> ProviderSearchResults:
            return ProviderSearchResults(
                (),
                (SearchDiagnostic(self.source_id, frozenset(), "item_skipped"),),
            )

    results = SearchCoordinator((First(), Second(), Third())).search(
        SearchQuery(text="river", bbox=(139, 35, 140, 36))
    )

    assert results.keys() == ("first", "third")
    assert tuple(results) == first_results
    assert [item.source_id for item in results.diagnostics] == [
        "first",
        "second",
        "second",
        "third",
        "third",
    ]
    assert [item.reason for item in results.diagnostics] == [
        "unsupported",
        "unsupported",
        "provider_failure",
        "unsupported",
        "item_skipped",
    ]
    assert [item.source_id for item in results.executions] == [
        "first",
        "second",
        "third",
    ]
    assert [item.result_count for item in results.executions] == [2, 0, 0]


def test_provider_concurrency_is_bounded_to_four() -> None:
    release = Event()
    four_started = Event()
    guard = Lock()
    active = 0
    maximum = 0

    class Blocking(SearchableAdapter):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.source_id = f"provider-{index}"

        def search(self, query: SearchQuery) -> tuple[object, ...]:
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
                if active == 4:
                    four_started.set()
            try:
                assert release.wait(5), "test did not release provider searches"
                return (object(),)
            finally:
                with guard:
                    active -= 1

    with ThreadPoolExecutor(max_workers=1) as runner:
        future = runner.submit(
            SearchCoordinator(tuple(Blocking(i) for i in range(12))).search,
            SearchQuery(text="river"),
        )
        try:
            assert four_started.wait(5), "four providers did not overlap"
        finally:
            release.set()
        results = future.result(timeout=5)

    assert maximum == 4
    assert len(results) == 12
    assert results.keys() == tuple(f"provider-{i}" for i in range(12))
