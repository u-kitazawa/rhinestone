from datetime import datetime, timezone
from typing import Any, Dict, cast

import pytest

from rhinestone.errors import ConfigValidationError, ExecutionAdapterUnavailableError
from rhinestone.models import (
    Config,
    FileAccessPlan,
    Metadata,
    Provenance,
    Resource,
    ResourceCandidate,
    SearchResult,
    Source,
    SourceDefinition,
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
        SourceDefinition("", "ckan")
    with pytest.raises(ConfigValidationError, match="adapter_type"):
        SourceDefinition("catalog", "")
    with pytest.raises(ConfigValidationError, match="source_id"):
        Config("", {})


def test_source_definition_is_deeply_immutable() -> None:
    settings: Dict[str, Any] = {"endpoint": "https://example.jp", "nested": {"x": 1}}
    source = SourceDefinition("catalog", "ckan", settings)
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
    metadata = Metadata(title="Population", raw={"table": "raw-value"})
    provenance = Provenance(provider="estat", raw={"query": "population"})
    result = SearchResult(
        title="Population",
        description="Official statistics",
        source_id="estat",
        settings={"stats_data_id": "0000000000"},
        metadata=metadata,
        provenance=provenance,
    )

    config = result.to_config()

    assert config == Config(source_id="estat", settings={"stats_data_id": "0000000000"})
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
        source_id="direct",
        settings={},
        metadata=Metadata(raw={}),
        provenance=Provenance(provider="direct", raw={}),
    )

    with pytest.raises(ConfigValidationError, match="not bound"):
        result.resolve()
