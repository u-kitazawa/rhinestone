"""Federated search over capable source adapters."""

from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import replace
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Mapping,
    Tuple,
    Union,
    overload,
)

from .models import Resource, Result, SearchDiagnostic, SearchQuery


class SearchResults(Sequence[Result]):
    """Provider-grouped results with deterministic sequence traversal.

    Integer indexing and iteration concatenate groups in their supplied order and
    preserve each provider's result order. The concatenated sequence is not a
    relevance ranking across providers; use source-grouped access when provider
    ranking semantics matter.
    """

    def __init__(
        self,
        grouped: Mapping[str, Tuple[Result, ...]],
        diagnostics: Iterable[SearchDiagnostic] = (),
    ) -> None:
        self._grouped = OrderedDict(
            (source_id, tuple(results)) for source_id, results in grouped.items()
        )
        self._items = tuple(
            result for results in self._grouped.values() for result in results
        )
        self._diagnostics = tuple(diagnostics)

    @classmethod
    def from_grouped(
        cls,
        grouped: Mapping[str, Tuple[Result, ...]],
        diagnostics: Iterable[SearchDiagnostic] = (),
    ) -> "SearchResults":
        return cls(grouped, diagnostics)

    @property
    def diagnostics(self) -> Tuple[SearchDiagnostic, ...]:
        """Return source-scoped diagnostics for the executed search."""
        return self._diagnostics

    @overload
    def __getitem__(self, index: int) -> Result: ...

    @overload
    def __getitem__(self, index: slice) -> Tuple[Result, ...]: ...

    @overload
    def __getitem__(self, index: str) -> Tuple[Result, ...]: ...

    def __getitem__(
        self, index: Union[int, slice, str]
    ) -> Union[Result, Tuple[Result, ...]]:
        if isinstance(index, str):
            return self._grouped[index]
        return self._items[index]

    def __len__(self) -> int:
        return len(self._items)

    def keys(self) -> Tuple[str, ...]:
        """Return source IDs in sequence traversal order."""
        return tuple(self._grouped)

    def values(self) -> Tuple[Tuple[Result, ...], ...]:
        """Return result groups in sequence traversal order."""
        return tuple(self._grouped.values())

    def items(self) -> Tuple[Tuple[str, Tuple[Result, ...]], ...]:
        """Return source IDs and result groups in sequence traversal order."""
        return tuple(self._grouped.items())

    def get(
        self, source_id: str, default: Tuple[Result, ...] = ()
    ) -> Tuple[Result, ...]:
        """Get one source group without requiring the source to exist."""
        return self._grouped.get(source_id, default)

    def bind_resolver(self, resolver: Callable[[Result], Resource]) -> "SearchResults":
        """Bind direct Result resolution to an application context."""
        grouped = OrderedDict(
            (
                source_id,
                tuple(
                    replace(
                        result,
                        _resolver=lambda result=result: resolver(result),
                    )
                    for result in results
                ),
            )
            for source_id, results in self._grouped.items()
        )
        return SearchResults(grouped, self._diagnostics)


class SearchCoordinator:
    """Search capable adapters in configuration order without cross-source ranking."""

    def __init__(self, adapters: Iterable[Any]) -> None:
        self._adapters = tuple(adapters)

    def search(self, query: SearchQuery) -> SearchResults:
        searchable = [
            adapter
            for adapter in self._adapters
            if getattr(adapter, "searchable", True)
            and callable(getattr(adapter, "search", None))
            and hasattr(adapter, "search_conditions")
        ]
        grouped: OrderedDict[str, Tuple[Any, ...]] = OrderedDict()
        diagnostics: List[SearchDiagnostic] = []
        for adapter in searchable:
            supported = frozenset(adapter.search_conditions)
            unsupported = query.supplied_conditions - supported
            required = frozenset(getattr(adapter, "required_search_conditions", ()))
            missing_required = required - query.supplied_conditions
            if unsupported or missing_required:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=adapter.source_id,
                        skipped_conditions=unsupported,
                        reason=(
                            "missing_required" if missing_required else "unsupported"
                        ),
                        missing_conditions=missing_required,
                    )
                )
            if missing_required:
                continue
            if query.supplied_conditions and not query.supplied_conditions & supported:
                continue
            grouped[adapter.source_id] = tuple(adapter.search(query.project(supported)))
        return SearchResults.from_grouped(grouped, diagnostics)
