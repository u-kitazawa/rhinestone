from datetime import datetime, timezone
from typing import Any, Dict, cast

import pytest

from rhinestone.errors import ExecutionAdapterUnavailableError
from rhinestone.models import (
    Config,
    FileAccessPlan,
    Metadata,
    Provenance,
    Resource,
    ResourceCandidate,
    SearchResult,
    Source,
)


def test_config_is_immutable_and_copies_nested_provider_settings() -> None:
    """Config の実行時変化が再現性を壊すため、深い不変性が必要である。"""
    settings: Dict[str, Any] = {
        "endpoint": "https://example.jp",
        "filters": {"year": 2024},
    }
    config = Config(source_type="ckan", settings=settings)

    cast(Dict[str, int], settings["filters"])["year"] = 2025

    assert config.settings["filters"]["year"] == 2024
    with pytest.raises(TypeError):
        cast(Dict[str, Any], config.settings)["resource_id"] = "changed"


def test_config_freezes_all_mutable_container_shapes() -> None:
    """Provider 設定内の list・tuple・set 経由でも Config を変更不能にするために必要である。"""
    config = Config(
        source_type="fixture",
        settings={"list": [1], "tuple": ({"nested": True},), "set": {1, 2}},
    )

    assert config.settings == {
        "list": (1,),
        "tuple": ({"nested": True},),
        "set": frozenset({1, 2}),
    }


def test_resource_preserves_source_metadata_and_provenance() -> None:
    """解決後に URI だけを返して確定済み知識を失わないために必要である。"""
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


def test_search_result_returns_provider_config_without_losing_knowledge() -> None:
    """検索結果が通常の検証・解決経路を迂回しないため Config 変換が必要である。"""
    metadata = Metadata(title="Population", raw={"table": "raw-value"})
    provenance = Provenance(provider="estat", raw={"query": "population"})
    result = SearchResult(
        title="Population",
        description="Official statistics",
        source_type="estat",
        provider_settings={"stats_data_id": "0000000000"},
        metadata=metadata,
        provenance=provenance,
    )

    config = result.to_config()

    assert config == Config(
        source_type="estat", settings={"stats_data_id": "0000000000"}
    )
    assert result.metadata is metadata
    assert result.provenance is provenance


def test_unbound_resource_cannot_open_without_execution_context() -> None:
    """解決だけを行ったResourceが暗黙runtimeやグローバル状態へfallbackしないために必要である。"""
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
        resource.open()
