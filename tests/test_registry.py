import pytest

from rhinestone.errors import (
    AdapterRegistrationError,
    RuntimeAdapterUnavailableError,
    UnsupportedProviderError,
)
from rhinestone.models import AccessPlan, Reference, Resource
from rhinestone.registry import AdapterRegistry
from rhinestone.security import DestinationPolicy


class ProviderAdapter:
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def load(self, reference: Reference) -> Resource:
        raise NotImplementedError


class RuntimeAdapter:
    priority = 0

    def __init__(self, name: str) -> None:
        self.name = name

    def supports(self, plan: AccessPlan) -> bool:
        return False

    def open(
        self,
        plan: AccessPlan,
        runtime: object,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> object:
        raise NotImplementedError


def test_registry_keeps_source_and_runtime_adapters_separate() -> None:
    """データ提供元の解釈と OSS 向け実行翻訳を混同しないために必要である。"""
    source = ProviderAdapter("ckan")
    execution = RuntimeAdapter("gdal")
    registry = AdapterRegistry(
        provider_adapters=(source,), runtime_adapters=(execution,)
    )

    assert registry.provider("ckan") is source
    assert registry.runtime("gdal") is execution


def test_duplicate_adapter_identity_is_rejected() -> None:
    """同じ識別子の実装が登録順で上書きされ、選択が非決定的になるのを防ぐために必要である。"""
    first = ProviderAdapter("ckan")
    second = ProviderAdapter("ckan")

    with pytest.raises(AdapterRegistrationError, match="ckan"):
        AdapterRegistry(provider_adapters=(first, second), runtime_adapters=())


def test_unknown_adapter_lookup_has_a_domain_specific_failure() -> None:
    """未登録 Source を汎用 KeyError にせず、呼び出し側が安定して判別するために必要である。"""
    registry = AdapterRegistry(provider_adapters=(), runtime_adapters=())

    with pytest.raises(UnsupportedProviderError, match="missing-source"):
        registry.provider("missing-source")


def test_unknown_execution_adapter_has_a_domain_specific_failure() -> None:
    """実行 Adapter 不足を Source 不足や汎用 KeyError と区別するために必要である。"""
    registry = AdapterRegistry(provider_adapters=(), runtime_adapters=())

    with pytest.raises(RuntimeAdapterUnavailableError, match="gdal"):
        registry.runtime("gdal")
