import pytest

from rhinestone.errors import (
    AdapterRegistrationError,
    ExecutionAdapterUnavailableError,
    UnsupportedSourceError,
)
from rhinestone.registry import AdapterRegistry


class SourceAdapter:
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id


class ExecutionAdapter:
    def __init__(self, name: str) -> None:
        self.name = name


def test_registry_keeps_source_and_execution_adapters_separate() -> None:
    """データ提供元の解釈と OSS 向け実行翻訳を混同しないために必要である。"""
    source = SourceAdapter("ckan")
    execution = ExecutionAdapter("gdal")
    registry = AdapterRegistry(
        source_adapters=(source,), execution_adapters=(execution,)
    )

    assert registry.source("ckan") is source
    assert registry.execution("gdal") is execution


def test_duplicate_adapter_identity_is_rejected() -> None:
    """同じ識別子の実装が登録順で上書きされ、選択が非決定的になるのを防ぐために必要である。"""
    first = SourceAdapter("ckan")
    second = SourceAdapter("ckan")

    with pytest.raises(AdapterRegistrationError, match="ckan"):
        AdapterRegistry(source_adapters=(first, second), execution_adapters=())


def test_unknown_adapter_lookup_has_a_domain_specific_failure() -> None:
    """未登録 Source を汎用 KeyError にせず、呼び出し側が安定して判別するために必要である。"""
    registry = AdapterRegistry(source_adapters=(), execution_adapters=())

    with pytest.raises(UnsupportedSourceError, match="missing-source"):
        registry.source("missing-source")


def test_unknown_execution_adapter_has_a_domain_specific_failure() -> None:
    """実行 Adapter 不足を Source 不足や汎用 KeyError と区別するために必要である。"""
    registry = AdapterRegistry(source_adapters=(), execution_adapters=())

    with pytest.raises(ExecutionAdapterUnavailableError, match="gdal"):
        registry.execution("gdal")
