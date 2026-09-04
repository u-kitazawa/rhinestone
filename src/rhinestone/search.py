"""Federated search over capable source adapters."""

from collections import OrderedDict
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Tuple

from .errors import UnsupportedSearchConditionError
from .models import SearchQuery


class SearchCoordinator:
    def __init__(self, adapters: Iterable[Any]) -> None:
        self._adapters = tuple(adapters)

    def search(self, query: SearchQuery) -> Mapping[str, Tuple[Any, ...]]:
        searchable = [
            adapter
            for adapter in self._adapters
            if callable(getattr(adapter, "search", None))
            and hasattr(adapter, "search_conditions")
        ]
        unsupported_by_adapter: Dict[str, FrozenSet[str]] = {}
        for adapter in searchable:
            unsupported = query.supplied_conditions - frozenset(
                adapter.search_conditions
            )
            if unsupported:
                unsupported_by_adapter[adapter.source_type] = unsupported
        if unsupported_by_adapter:
            details = ", ".join(
                "{}: {}".format(name, ", ".join(sorted(conditions)))
                for name, conditions in sorted(unsupported_by_adapter.items())
            )
            raise UnsupportedSearchConditionError(
                f"Unsupported search conditions ({details})"
            )
        grouped: OrderedDict[str, Tuple[Any, ...]] = OrderedDict()
        for adapter in sorted(searchable, key=lambda item: item.source_type):
            grouped[adapter.source_type] = tuple(adapter.search(query))
        return grouped
