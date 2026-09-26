"""Federated search over capable source adapters."""

from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from time import perf_counter
from typing import (
    Any,
    cast,
    overload,
)

from .errors import (
    CredentialUnavailableError,
    KnowledgeResolutionError,
    KnowledgeValidationError,
    ProviderMetadataError,
    ProviderResponseError,
)
from .models import Resource, Result, SearchDiagnostic, SearchExecution, SearchQuery


class SearchResults(Sequence[Result]):
    """Provider-grouped results with deterministic sequence traversal.

    Integer indexing and iteration concatenate groups in their supplied order and
    preserve each provider's result order. The concatenated sequence is not a
    relevance ranking across providers; use source-grouped access when provider
    ranking semantics matter.
    """

    def __init__(
        self,
        grouped: Mapping[str, tuple[Result, ...]],
        diagnostics: Iterable[SearchDiagnostic] = (),
        executions: Iterable[SearchExecution] = (),
    ) -> None:
        self._results_by_source = OrderedDict(
            (source_id, tuple(results)) for source_id, results in grouped.items()
        )
        self._flattened_results = tuple(
            result for results in self._results_by_source.values() for result in results
        )
        self._diagnostics = tuple(diagnostics)
        self._executions = tuple(executions)

    @classmethod
    def from_grouped(
        cls,
        grouped: Mapping[str, tuple[Result, ...]],
        diagnostics: Iterable[SearchDiagnostic] = (),
        executions: Iterable[SearchExecution] = (),
    ) -> "SearchResults":
        """Build immutable results from source-grouped Result tuples."""
        return cls(grouped, diagnostics, executions)

    @property
    def diagnostics(self) -> tuple[SearchDiagnostic, ...]:
        """Return source-scoped diagnostics for the executed search."""
        return self._diagnostics

    @property
    def executions(self) -> tuple[SearchExecution, ...]:
        """Return provider search timings in configured execution order."""

        return self._executions

    @overload
    def __getitem__(self, index: int) -> Result: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Result, ...]: ...

    @overload
    def __getitem__(self, index: str) -> tuple[Result, ...]: ...

    def __getitem__(self, index: int | slice | str) -> Result | tuple[Result, ...]:
        """Return a result, sequence slice, or source-specific result group."""
        if isinstance(index, str):
            return self._results_by_source[index]
        return self._flattened_results[index]

    def __len__(self) -> int:
        """Return the total number of results across all source groups."""
        return len(self._flattened_results)

    def keys(self) -> tuple[str, ...]:
        """Return source IDs in sequence traversal order."""
        return tuple(self._results_by_source)

    def values(self) -> tuple[tuple[Result, ...], ...]:
        """Return result groups in sequence traversal order."""
        return tuple(self._results_by_source.values())

    def items(self) -> tuple[tuple[str, tuple[Result, ...]], ...]:
        """Return source IDs and result groups in sequence traversal order."""
        return tuple(self._results_by_source.items())

    def get(
        self, source_id: str, default: tuple[Result, ...] = ()
    ) -> tuple[Result, ...]:
        """Get one source group without requiring the source to exist."""
        return self._results_by_source.get(source_id, default)

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
            for source_id, results in self._results_by_source.items()
        )
        return SearchResults(grouped, self._diagnostics, self._executions)


class SearchCoordinator:
    """Search capable adapters in configuration order without cross-source ranking."""

    def __init__(self, adapters: Iterable[Any], knowledge: Any | None = None) -> None:
        self._adapters = tuple(adapters)
        self._knowledge = knowledge

    def search(self, query: SearchQuery) -> SearchResults:
        """Search capable adapters and isolate expected provider failures.

        Each source receives only the conditions it declares. Unsupported or
        missing required conditions become diagnostics; metadata and response
        failures affect only the failing source. Unexpected programming errors
        continue to propagate.
        """
        searchable_adapters = [
            adapter
            for adapter in self._adapters
            if getattr(adapter, "searchable", True)
            and callable(getattr(adapter, "search", None))
            and hasattr(adapter, "search_conditions")
        ]
        grouped_results: OrderedDict[str, tuple[Any, ...]] = OrderedDict()
        diagnostics: list[SearchDiagnostic] = []
        executions: list[SearchExecution] = []
        resolved_area: Any | None = None
        if query.area is not None:
            try:
                if self._knowledge is None:
                    raise KnowledgeResolutionError(
                        "area knowledge adapter is not configured"
                    )
                resolved_area = self._knowledge.resolve_area(query.area)
            except (KnowledgeResolutionError, KnowledgeValidationError):
                return SearchResults.from_grouped(
                    grouped_results,
                    (
                        SearchDiagnostic(
                            source_id=adapter.source_id,
                            skipped_conditions=frozenset({"area"}),
                            reason="area_resolution_failed",
                        )
                        for adapter in searchable_adapters
                    ),
                )

        for adapter in searchable_adapters:
            supported_conditions = frozenset(adapter.search_conditions)
            projected_query = query
            area_handled = False
            if resolved_area is not None:
                if "bbox" in supported_conditions:
                    projected_query = replace(
                        query,
                        area=None,
                        bbox=resolved_area.bbox.as_tuple(),
                    )
                    area_handled = True
                elif (
                    "text" in supported_conditions
                    and bool(getattr(adapter, "area_text_fallback", False))
                ):
                    text = resolved_area.canonical_name
                    if query.text:
                        text = f"{query.text} {text}"
                    projected_query = replace(query, area=None, text=text)
                    area_handled = True
                else:
                    projected_query = replace(query, area=None)

            unsupported_conditions = query.supplied_conditions - supported_conditions
            if area_handled:
                unsupported_conditions -= {"area"}
            required_conditions = frozenset(
                cast(Iterable[str], getattr(adapter, "required_search_conditions", ()))
            )
            missing_required_conditions = (
                required_conditions - projected_query.supplied_conditions
            )
            if unsupported_conditions or missing_required_conditions:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=adapter.source_id,
                        skipped_conditions=unsupported_conditions,
                        reason=(
                            "missing_required"
                            if missing_required_conditions
                            else "unsupported"
                        ),
                        missing_conditions=missing_required_conditions,
                    )
                )
            if missing_required_conditions:
                continue
            if (
                query.supplied_conditions
                and not projected_query.supplied_conditions & supported_conditions
            ):
                continue
            started = perf_counter()
            provider_results: tuple[Any, ...] = ()
            try:
                provider_results = tuple(
                    adapter.search(projected_query.project(supported_conditions))
                )
                grouped_results[adapter.source_id] = provider_results
            except ProviderMetadataError:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=adapter.source_id,
                        skipped_conditions=frozenset(),
                        reason="provider_failure",
                        failure_type="metadata",
                    )
                )
            except ProviderResponseError:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=adapter.source_id,
                        skipped_conditions=frozenset(),
                        reason="provider_failure",
                        failure_type="response",
                    )
                )
            except CredentialUnavailableError:
                diagnostics.append(
                    SearchDiagnostic(
                        source_id=adapter.source_id,
                        skipped_conditions=frozenset(),
                        reason="provider_failure",
                        failure_type="credential",
                    )
                )
            finally:
                executions.append(
                    SearchExecution(
                        source_id=adapter.source_id,
                        elapsed_ms=(perf_counter() - started) * 1000,
                        result_count=len(provider_results),
                    )
                )
        return SearchResults.from_grouped(grouped_results, diagnostics, executions)
