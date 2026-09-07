"""Federated search over capable source adapters."""

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import replace
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    Mapping,
    Tuple,
    Union,
    overload,
)

from .errors import UnsupportedSearchConditionError
from .models import Config, Resource, Result, SearchQuery


class Results(Sequence[SearchResult]):
    """Sequence-like search results with optional source-grouped access."""

    def __init__(self, grouped: Mapping[str, Tuple[SearchResult, ...]]) -> None:
        self._grouped = OrderedDict(
            (source_id, tuple(results)) for source_id, results in grouped.items()
        )
        self._items = tuple(
            result for results in self._grouped.values() for result in results
        )

    @classmethod
    def from_grouped(
        cls, grouped: Mapping[str, Tuple[SearchResult, ...]]
    ) -> "SearchResults":
        return cls(grouped)

    @overload
    def __getitem__(self, index: int) -> SearchResult: ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[SearchResult, ...]: ...

    @overload
    def __getitem__(self, index: str) -> Tuple[SearchResult, ...]: ...

    def __getitem__(
        self, index: Union[int, slice, str]
    ) -> Union[SearchResult, Tuple[SearchResult, ...]]:
        if isinstance(index, str):
            return self._grouped[index]
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def keys(self) -> Tuple[str, ...]:
        """Return source IDs for advanced source-grouped access."""
        return tuple(self._grouped)

    def values(self) -> Tuple[Tuple[SearchResult, ...], ...]:
        """Return result groups for advanced source-grouped access."""
        return tuple(self._grouped.values())

    def items(self) -> Tuple[Tuple[str, Tuple[SearchResult, ...]], ...]:
        """Return source IDs and result groups for advanced access."""
        return tuple(self._grouped.items())

    def get(
        self, source_id: str, default: Tuple[SearchResult, ...] = ()
    ) -> Tuple[SearchResult, ...]:
        """Get one source group without requiring the source to exist."""
        return self._grouped.get(source_id, default)

    def bind_resolver(self, resolver: Callable[[Config], Resource]) -> "SearchResults":
        """Bind direct SearchResult resolution to an application context."""
        grouped = OrderedDict(
            (
                source_id,
                tuple(
                    replace(
                        result,
                        _resolver=lambda result=result: resolver(result.to_config()),
                    )
                    for result in results
                ),
            )
            for source_id, results in self._grouped.items()
        )
        return SearchResults(grouped)


class SearchCoordinator:
    def __init__(self, adapters: Iterable[Any]) -> None:
        self._adapters = tuple(adapters)

    def search(self, query: SearchQuery) -> Mapping[str, Tuple[Any, ...]]:
        searchable = [
            adapter
            for adapter in self._adapters
            if getattr(adapter, "searchable", True)
            and callable(getattr(adapter, "search", None))
            and hasattr(adapter, "search_conditions")
        ]
        unsupported_by_adapter: Dict[str, FrozenSet[str]] = {}
        for adapter in searchable:
            unsupported = query.supplied_conditions - frozenset(
                adapter.search_conditions
            )
            if unsupported:
                unsupported_by_adapter[adapter.source_id] = unsupported
        if unsupported_by_adapter:
            details = ", ".join(
                "{}: {}".format(name, ", ".join(sorted(conditions)))
                for name, conditions in sorted(unsupported_by_adapter.items())
            )
            raise UnsupportedSearchConditionError(
                f"Unsupported search conditions ({details})"
            )
        grouped: OrderedDict[str, Tuple[Any, ...]] = OrderedDict()
        for adapter in sorted(searchable, key=lambda item: item.source_id):
            grouped[adapter.source_id] = tuple(adapter.search(query))
        return grouped
