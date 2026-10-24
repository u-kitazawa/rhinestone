import pytest

from rhinestone.errors import AdapterRegistrationError, RuntimeAdapterUnavailableError
from rhinestone.models import (
    AccessPlan,
)
from rhinestone.runtime import RuntimeAdapterSelector
from rhinestone.security import DestinationPolicy


class FakeRuntimeAdapter:
    def __init__(self, name: str, priority: int, supported_format: str) -> None:
        self.name = name
        self.priority = priority
        self.supported_format = supported_format

    def supports(self, plan: AccessPlan) -> bool:
        return plan.format == self.supported_format

    def open(
        self,
        plan: AccessPlan,
        runtime: object,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> object:
        return runtime


def resource(format_name: str = "shapefile") -> AccessPlan:
    return AccessPlan(kind="file", uri="https://example.test/data", format=format_name)


def test_execution_selection_is_deterministic_across_registration_order() -> None:
    """偶然の登録順ではなく説明可能な優先度で Runtime Adapter を選ぶために必要である。"""
    gdal = FakeRuntimeAdapter("gdal", priority=20, supported_format="shapefile")
    pyogrio = FakeRuntimeAdapter("pyogrio", priority=10, supported_format="shapefile")
    forward = RuntimeAdapterSelector((pyogrio, gdal)).select(resource())
    reverse = RuntimeAdapterSelector((gdal, pyogrio)).select(resource())

    assert forward is gdal
    assert reverse is gdal


def test_user_can_explicitly_select_an_available_adapter() -> None:
    """自動選択が適さない場合に公開 API の明示指定を尊重するために必要である。"""
    gdal = FakeRuntimeAdapter("gdal", priority=20, supported_format="shapefile")
    pyogrio = FakeRuntimeAdapter("pyogrio", priority=10, supported_format="shapefile")

    selected = RuntimeAdapterSelector((gdal, pyogrio)).select(
        resource(), requested="pyogrio"
    )

    assert selected is pyogrio


def test_unavailable_requested_adapter_has_a_specific_failure() -> None:
    """明示指定の失敗を format や依存不足と区別できるようにするために必要である。"""
    gdal = FakeRuntimeAdapter("gdal", priority=20, supported_format="shapefile")

    with pytest.raises(RuntimeAdapterUnavailableError, match="rasterio"):
        RuntimeAdapterSelector((gdal,)).select(resource(), requested="rasterio")


def test_no_compatible_automatic_adapter_fails_explicitly() -> None:
    """対応 runtime がないとき暗黙の fallback や import を行わないために必要である。"""
    gdal = FakeRuntimeAdapter("gdal", priority=20, supported_format="shapefile")

    with pytest.raises(RuntimeAdapterUnavailableError, match="No runtime"):
        RuntimeAdapterSelector((gdal,)).select(resource("geojson"))


def test_selector_rejects_duplicate_names_instead_of_overwriting() -> None:
    first = FakeRuntimeAdapter("same", priority=10, supported_format="shapefile")
    second = FakeRuntimeAdapter("same", priority=20, supported_format="shapefile")
    with pytest.raises(AdapterRegistrationError, match="unique"):
        RuntimeAdapterSelector((first, second))
