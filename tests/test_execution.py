from typing import FrozenSet

import pytest

from rhinestone.errors import ExecutionAdapterUnavailableError
from rhinestone.execution import ExecutionAdapterSelector


class FakeExecutionAdapter:
    def __init__(self, name: str, priority: int, supported_format: str) -> None:
        self.name = name
        self.priority = priority
        self.supported_format = supported_format

    def supports(self, resource: object, dependencies: FrozenSet[str]) -> bool:
        return (
            getattr(resource, "format", None) == self.supported_format
            and self.name in dependencies
        )


class FakeResource:
    format = "shapefile"


def test_execution_selection_is_deterministic_across_registration_order() -> None:
    """偶然の登録順ではなく説明可能な優先度で Execution Adapter を選ぶために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")
    pyogrio = FakeExecutionAdapter("pyogrio", priority=10, supported_format="shapefile")
    dependencies = frozenset({"gdal", "pyogrio"})

    forward = ExecutionAdapterSelector((pyogrio, gdal)).select(
        FakeResource(), dependencies
    )
    reverse = ExecutionAdapterSelector((gdal, pyogrio)).select(
        FakeResource(), dependencies
    )

    assert forward is gdal
    assert reverse is gdal


def test_user_can_explicitly_select_an_available_adapter() -> None:
    """自動選択が適さない場合に公開 API の明示指定を尊重するために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")
    pyogrio = FakeExecutionAdapter("pyogrio", priority=10, supported_format="shapefile")

    selected = ExecutionAdapterSelector((gdal, pyogrio)).select(
        FakeResource(), frozenset({"gdal", "pyogrio"}), requested="pyogrio"
    )

    assert selected is pyogrio


def test_unavailable_requested_adapter_has_a_specific_failure() -> None:
    """明示指定の失敗を format や依存不足と区別できるようにするために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")

    with pytest.raises(ExecutionAdapterUnavailableError, match="rasterio"):
        ExecutionAdapterSelector((gdal,)).select(
            FakeResource(), frozenset({"gdal"}), requested="rasterio"
        )


def test_no_compatible_automatic_adapter_fails_explicitly() -> None:
    """対応 runtime がないとき暗黙の fallback や import を行わないために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")

    with pytest.raises(ExecutionAdapterUnavailableError, match="No execution"):
        ExecutionAdapterSelector((gdal,)).select(FakeResource(), frozenset())
