from typing import List

import pytest

from rhinestone.errors import (
    ConfigValidationError,
    ProviderMetadataError,
    UnsupportedSourceError,
)
from rhinestone.models import Config, Metadata, Provenance, ResourceCandidate, Source
from rhinestone.pipeline import AccessPipeline
from rhinestone.resolution import Resolver


class RecordingSourceAdapter:
    source_type = "fixture"

    def __init__(self, events: List[str]) -> None:
        self.events = events

    def load(self, config: Config) -> Source:
        self.events.append("source-adapter")
        return Source(
            metadata=Metadata(title="Dataset", raw={"original": True}),
            candidates=(
                ResourceCandidate("https://example.jp/data.csv", "csv", "text/csv"),
            ),
            capabilities=frozenset({"download"}),
            provenance=Provenance(provider="fixture", raw={"request": "known"}),
            raw_metadata={"original": True},
        )


class RecordingResolver(Resolver):
    def __init__(self, events: List[str]) -> None:
        super().__init__()
        self.events = events

    def resolve(self, source: Source):
        self.events.append("resolver")
        return super().resolve(source)


def test_access_pipeline_keeps_source_interpretation_before_resolution() -> None:
    """Provider 解釈と Resource 選択の責務境界・処理順序を維持するために必要である。"""
    events: List[str] = []
    pipeline = AccessPipeline(
        source_adapters=(RecordingSourceAdapter(events),),
        resolver=RecordingResolver(events),
    )
    config = Config(source_type="fixture", settings={"dataset": "data-1"})

    resource = pipeline.resolve(config)

    assert events == ["source-adapter", "resolver"]
    assert resource.source.raw_metadata == {"original": True}
    assert resource.provenance.raw == {"request": "known"}
    assert config == Config(source_type="fixture", settings={"dataset": "data-1"})


def test_unknown_source_type_has_a_specific_failure() -> None:
    """未知 provider を別 Adapter や URL へ推測せず明示的に拒否するために必要である。"""
    pipeline = AccessPipeline(source_adapters=(), resolver=Resolver())

    with pytest.raises(UnsupportedSourceError, match="unknown"):
        pipeline.resolve(Config(source_type="unknown", settings={}))


def test_provider_failure_is_wrapped_without_losing_its_cause() -> None:
    """外部 metadata 取得失敗を内部不変条件違反と区別し、原因も追跡するために必要である。"""
    provider_error = OSError("connection closed")

    class BrokenAdapter:
        source_type = "broken"

        def load(self, config: Config) -> Source:
            raise provider_error

    pipeline = AccessPipeline(source_adapters=(BrokenAdapter(),), resolver=Resolver())

    with pytest.raises(ProviderMetadataError) as captured:
        pipeline.resolve(Config(source_type="broken", settings={}))

    assert captured.value.__cause__ is provider_error


def test_pipeline_does_not_wrap_an_expected_domain_error() -> None:
    """Config 不正を metadata 通信失敗へ誤分類しないために必要である。"""
    expected = ConfigValidationError("dataset is required")

    class RejectingAdapter:
        source_type = "rejecting"

        def load(self, config: Config) -> Source:
            raise expected

    pipeline = AccessPipeline(
        source_adapters=(RejectingAdapter(),), resolver=Resolver()
    )

    with pytest.raises(ConfigValidationError) as captured:
        pipeline.resolve(Config(source_type="rejecting", settings={}))

    assert captured.value is expected


def test_duplicate_source_adapters_are_rejected_by_pipeline() -> None:
    """同じ Source type の選択が登録順依存になることを防ぐために必要である。"""
    events: List[str] = []
    pipeline = AccessPipeline(
        source_adapters=(
            RecordingSourceAdapter(events),
            RecordingSourceAdapter(events),
        ),
        resolver=Resolver(),
    )

    with pytest.raises(UnsupportedSourceError, match="ambiguous"):
        pipeline.resolve(Config(source_type="fixture", settings={}))
