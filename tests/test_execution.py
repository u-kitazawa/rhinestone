import pytest

from rhinestone.errors import ExecutionAdapterUnavailableError
from rhinestone.execution import ExecutionAdapterSelector
from rhinestone.models import (
    FileAccessPlan,
    Metadata,
    Provenance,
    Resource,
    ResourceCandidate,
    Source,
)
from rhinestone.security import DestinationPolicy


class FakeExecutionAdapter:
    def __init__(self, name: str, priority: int, supported_format: str) -> None:
        self.name = name
        self.priority = priority
        self.supported_format = supported_format

    def supports(self, resource: Resource) -> bool:
        return resource.format == self.supported_format

    def open(
        self,
        resource: Resource,
        runtime: object,
        *,
        destination_policy: DestinationPolicy | None = None,
    ) -> object:
        return runtime


def resource(format_name: str = "shapefile") -> Resource:
    candidate = ResourceCandidate(
        "https://example.test/data", format_name, "application/octet-stream"
    )
    source = Source(
        metadata=Metadata(raw={}),
        candidates=(candidate,),
        capabilities=frozenset(),
        provenance=Provenance(provider="fixture", raw={}),
        raw_metadata={},
    )
    return Resource(
        uri=candidate.uri,
        format=candidate.format,
        media_type=candidate.media_type,
        metadata=source.metadata,
        provenance=source.provenance,
        access_plan=FileAccessPlan(uri=candidate.uri),
        source=source,
    )


def test_execution_selection_is_deterministic_across_registration_order() -> None:
    """偶然の登録順ではなく説明可能な優先度で Execution Adapter を選ぶために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")
    pyogrio = FakeExecutionAdapter("pyogrio", priority=10, supported_format="shapefile")
    forward = ExecutionAdapterSelector((pyogrio, gdal)).select(resource())
    reverse = ExecutionAdapterSelector((gdal, pyogrio)).select(resource())

    assert forward is gdal
    assert reverse is gdal


def test_user_can_explicitly_select_an_available_adapter() -> None:
    """自動選択が適さない場合に公開 API の明示指定を尊重するために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")
    pyogrio = FakeExecutionAdapter("pyogrio", priority=10, supported_format="shapefile")

    selected = ExecutionAdapterSelector((gdal, pyogrio)).select(
        resource(), requested="pyogrio"
    )

    assert selected is pyogrio


def test_unavailable_requested_adapter_has_a_specific_failure() -> None:
    """明示指定の失敗を format や依存不足と区別できるようにするために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")

    with pytest.raises(ExecutionAdapterUnavailableError, match="rasterio"):
        ExecutionAdapterSelector((gdal,)).select(resource(), requested="rasterio")


def test_no_compatible_automatic_adapter_fails_explicitly() -> None:
    """対応 runtime がないとき暗黙の fallback や import を行わないために必要である。"""
    gdal = FakeExecutionAdapter("gdal", priority=20, supported_format="shapefile")

    with pytest.raises(ExecutionAdapterUnavailableError, match="No execution"):
        ExecutionAdapterSelector((gdal,)).select(resource("geojson"))
