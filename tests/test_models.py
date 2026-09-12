from datetime import datetime, timezone
from typing import Any, Dict, cast

import pytest

from rhinestone.errors import ConfigValidationError, ExecutionAdapterUnavailableError
from rhinestone.models import (
    Config,
    FileAccessPlan,
    Metadata,
    Provenance,
    Provider,
    Resource,
    ResourceCandidate,
    SearchDiagnostic,
    SearchQuery,
    SearchResult,
    Source,
)


def test_config_is_immutable_and_copies_nested_settings() -> None:
    settings: Dict[str, Any] = {
        "resource_id": "resource-1",
        "filters": {"year": 2024},
    }
    config = Config(source_id="ckan", settings=settings)

    cast(Dict[str, int], settings["filters"])["year"] = 2025

    assert config.settings["filters"]["year"] == 2024
    with pytest.raises(TypeError):
        cast(Dict[str, Any], config.settings)["resource_id"] = "changed"


def test_source_definition_and_config_ids_must_be_non_empty() -> None:
    with pytest.raises(ConfigValidationError, match="source id"):
        Provider("", "ckan")
    with pytest.raises(ConfigValidationError, match="adapter_type"):
        Provider("catalog", "")
    with pytest.raises(ConfigValidationError, match="source_id"):
        Config("", {})


@pytest.mark.parametrize("limit", (-1, True, 1.5, "1"))
def test_search_query_rejects_invalid_limits(limit: object) -> None:
    with pytest.raises(ConfigValidationError, match="limit"):
        SearchQuery(limit=cast(Any, limit))


@pytest.mark.parametrize(
    "bbox",
    (
        (),
        (0, 1, 2),
        (0, 1, 2, 3, 4),
        (0, 1, 2, "3"),
        (False, 1, 2, 3),
        [0, 1, 2, 3],
    ),
)
def test_search_query_rejects_invalid_bboxes(bbox: object) -> None:
    with pytest.raises(ConfigValidationError, match="bbox"):
        SearchQuery(bbox=cast(Any, bbox))


def test_search_query_bbox_error_does_not_call_element_repr() -> None:
    class Unrepresentable:
        def __repr__(self) -> str:
            raise AssertionError("repr must not be called")

    with pytest.raises(ConfigValidationError, match="invalid length or element type"):
        SearchQuery(bbox=cast(Any, (0, 1, 2, Unrepresentable())))


@pytest.mark.parametrize(
    "time",
    (
        (),
        (None,),
        (None, None, None),
        ("2024-01-01", None),
        [None, None],
    ),
)
def test_search_query_rejects_invalid_time_ranges(time: object) -> None:
    with pytest.raises(ConfigValidationError, match="time"):
        SearchQuery(time=cast(Any, time))


def test_search_query_time_error_does_not_call_element_repr() -> None:
    class Unrepresentable:
        def __repr__(self) -> str:
            raise AssertionError("repr must not be called")

    with pytest.raises(ConfigValidationError, match="invalid length or element type"):
        SearchQuery(time=cast(Any, (Unrepresentable(), None)))


def test_search_query_accepts_valid_boundary_values() -> None:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    query = SearchQuery(
        bbox=(0, 1.5, 2, 3.5),
        time=(start, None),
        limit=0,
    )

    assert query.bbox == (0, 1.5, 2, 3.5)
    assert query.time == (start, None)
    assert query.limit == 0


def test_source_definition_is_deeply_immutable() -> None:
    settings: Dict[str, Any] = {"endpoint": "https://example.jp", "nested": {"x": 1}}
    source = Provider("catalog", "ckan", settings)
    cast(Dict[str, int], settings["nested"])["x"] = 2

    assert source.settings["nested"]["x"] == 1
    with pytest.raises(TypeError):
        cast(Dict[str, Any], source.settings)["endpoint"] = "changed"


def test_config_freezes_all_mutable_container_shapes() -> None:
    config = Config(
        source_id="fixture",
        settings={"list": [1], "tuple": ({"nested": True},), "set": {1, 2}},
    )

    assert config.settings == {
        "list": (1,),
        "tuple": ({"nested": True},),
        "set": frozenset({1, 2}),
    }


def test_resource_preserves_source_metadata_and_provenance() -> None:
    raw = {"provider_only": {"encoding": "cp932"}}
    metadata = Metadata(title="River", raw=raw)
    provenance = Provenance(
        provider="example-ckan",
        resource_identifier="resource-1",
        retrieved_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        raw={"request_id": "req-1"},
    )
    candidate = ResourceCandidate(
        uri="https://example.jp/river.zip",
        format="shapefile",
        media_type="application/zip",
    )
    source = Source(
        metadata=metadata,
        candidates=(candidate,),
        capabilities=frozenset({"download"}),
        provenance=provenance,
        raw_metadata=raw,
    )

    resource = Resource(
        uri=candidate.uri,
        format=candidate.format,
        media_type=candidate.media_type,
        metadata=source.metadata,
        provenance=source.provenance,
        access_plan=FileAccessPlan(uri=candidate.uri, archive="zip"),
        source=source,
    )

    assert resource.metadata is metadata
    assert resource.provenance is provenance
    assert resource.source is source
    assert resource.source.raw_metadata == raw


def test_search_result_returns_config_without_losing_knowledge() -> None:
    metadata = Metadata(title="Dataset", raw={"table": "raw-value"})
    provenance = Provenance(provider="catalog", raw={"query": "dataset"})
    result = SearchResult(
        title="Dataset",
        description="Official dataset",
        discovered_by="search-ckan-jp",
        target=Config("catalog", {"resource_id": "resource-1"}),
        metadata=metadata,
        provenance=provenance,
    )

    config = result.to_config()

    assert config == Config(source_id="catalog", settings={"resource_id": "resource-1"})
    assert result.metadata is metadata
    assert result.provenance is provenance


def test_unbound_resource_cannot_open_without_execution_context() -> None:
    candidate = ResourceCandidate("/data/a.csv", "csv", "text/csv")
    source = Source(
        metadata=Metadata(title="A", raw={}),
        candidates=(candidate,),
        capabilities=frozenset(),
        provenance=Provenance(provider="direct", raw={}),
        raw_metadata={},
    )
    resource = Resource(
        uri=candidate.uri,
        format=candidate.format,
        media_type=candidate.media_type,
        metadata=source.metadata,
        provenance=source.provenance,
        access_plan=FileAccessPlan(uri=candidate.uri),
        source=source,
    )

    with pytest.raises(ExecutionAdapterUnavailableError, match="not bound"):
        resource.open("gdal")


def test_unbound_search_result_cannot_resolve() -> None:
    result = SearchResult(
        title="Dataset",
        description=None,
        discovered_by="catalog",
        target=Config("direct", {}),
        metadata=Metadata(raw={}),
        provenance=Provenance(provider="direct", raw={}),
    )

    with pytest.raises(ConfigValidationError, match="not bound"):
        result.resolve()


def test_search_result_requires_a_discovery_source() -> None:
    with pytest.raises(ConfigValidationError, match="discovered_by"):
        SearchResult(
            title="Dataset",
            description=None,
            discovered_by="",
            target=Config("direct", {}),
            metadata=Metadata(raw={}),
            provenance=Provenance(provider="direct", raw={}),
        )


def test_search_diagnostic_requires_a_source_id() -> None:
    with pytest.raises(ConfigValidationError, match="search diagnostic source_id"):
        SearchDiagnostic(source_id="", skipped_conditions=frozenset({"text"}))


def test_search_diagnostic_freezes_missing_conditions() -> None:
    diagnostic = SearchDiagnostic(
        source_id="source",
        skipped_conditions=frozenset({"bbox"}),
        reason="missing_required",
        missing_conditions=frozenset({"text"}),
    )

    assert diagnostic.missing_conditions == frozenset({"text"})


def test_search_diagnostic_can_describe_provider_failure() -> None:
    diagnostic = SearchDiagnostic(
        source_id="source",
        skipped_conditions=frozenset(),
        reason="provider_failure",
        failure_type="response",
    )

    assert diagnostic.failure_type == "response"
