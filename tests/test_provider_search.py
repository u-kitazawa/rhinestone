"""Provider scoping happens before search I/O, independently of format criteria."""

from typing import Any, cast

import pytest

from rhinestone import Format, ProviderId, api, configure, search
from rhinestone.catalogs import BUILTIN, Catalog
from rhinestone.errors import ConfigValidationError
from rhinestone.models import SearchQuery
from rhinestone.search import SearchCoordinator

from .test_search import OrderedSearchableAdapter, ResolveOnlyAdapter


def test_provider_ids_match_the_builtin_catalog() -> None:
    assert {value.value for value in ProviderId} == {p.id for p in BUILTIN}


def test_selection_is_frozen_and_is_not_a_provider_search_condition() -> None:
    providers = [ProviderId.GSI]
    query = SearchQuery(providers=providers)
    providers.clear()
    assert query.providers == (ProviderId.GSI,)
    assert query.supplied_conditions == frozenset()
    assert query.project({"text"}).providers is None


@pytest.mark.parametrize(
    "providers", ["gsi", ProviderId.GSI, 1, [None], [1], [""], [" "]]
)
def test_invalid_provider_arrays_are_rejected(providers: Any) -> None:
    with pytest.raises(ConfigValidationError, match="providers must be an array"):
        SearchQuery(providers=providers)


def test_selection_preserves_catalog_order_and_skips_other_adapters() -> None:
    first = OrderedSearchableAdapter("first", (object(),))
    skipped = OrderedSearchableAdapter("skipped", (object(),))
    last = OrderedSearchableAdapter("last", (object(),))
    coordinator = SearchCoordinator((first, skipped, last))

    results = coordinator.search(
        SearchQuery(text="river", providers=["last", "first", "first"])
    )

    assert results.keys() == ("first", "last")
    assert [execution.source_id for execution in results.executions] == [
        "first",
        "last",
    ]
    assert not results.diagnostics
    assert not skipped.queries
    assert len(first.queries) == len(last.queries) == 1
    assert first.queries[0].providers is None


def test_unknown_provider_fails_before_any_dispatch() -> None:
    selected = OrderedSearchableAdapter("selected", (object(),))
    with pytest.raises(ConfigValidationError, match="Unknown or unconfigured"):
        SearchCoordinator((selected,)).search(
            SearchQuery(providers=["selected", "unknown"])
        )
    assert not selected.queries


def test_resolve_only_provider_produces_no_search_execution() -> None:
    adapter = ResolveOnlyAdapter()
    results = SearchCoordinator((adapter,)).search(
        SearchQuery(providers=["resolve-only"], area="東京都")
    )
    assert not results
    assert not results.diagnostics
    assert not results.executions
    assert not adapter.called


def test_top_level_selection_avoids_all_remote_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unselected Provider performed I/O")

    monkeypatch.setattr(api._http, "get_json", fail_network)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(api._http, "get_text", fail_network)  # pyright: ignore[reportPrivateUsage]
    api._default_application.cache_clear()  # pyright: ignore[reportPrivateUsage]
    try:
        results = search(providers=[ProviderId.GSI])
        assert results.keys() == ("gsi",)
        assert not search(providers=[ProviderId.GSI], format=(Format.GEOJSON,))
        assert results[0].resolve().provenance.provider == "gsi"
        empty = search(providers=[], area="東京都")
        assert not empty
        assert not empty.diagnostics
        assert not empty.executions
    finally:
        api._default_application.cache_clear()  # pyright: ignore[reportPrivateUsage]


def test_app_and_query_support_the_same_provider_scope() -> None:
    app = configure(catalog=BUILTIN)
    shorthand = app.search(providers=[ProviderId.GSI])
    explicit = app.search(SearchQuery(providers=(ProviderId.GSI,)))
    assert shorthand.keys() == explicit.keys() == ("gsi",)
    assert [r.title for r in shorthand] == [r.title for r in explicit]


def test_unconfigured_enum_and_query_shorthand_conflict_are_errors() -> None:
    app = configure(catalog=Catalog(()))
    with pytest.raises(ConfigValidationError, match="Unknown or unconfigured"):
        app.search(providers=[ProviderId.GSI])
    with pytest.raises(TypeError, match="either query or search parameters"):
        app.search(SearchQuery(), providers=[ProviderId.GSI])
    with pytest.raises(ConfigValidationError, match="providers must be an array"):
        app.search(providers=cast(Any, "gsi"))
