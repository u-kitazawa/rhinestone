from typing import List, Tuple

from rhinestone.adapters.execution import GdalAdapter, PyogrioAdapter
from rhinestone.adapters.source.direct import DirectAdapter
from rhinestone.execution import ExecutionAdapterSelector
from rhinestone.models import Config
from rhinestone.pipeline import AccessPipeline
from rhinestone.registry import DependencyRegistry
from rhinestone.resolution import Resolver


class FakeGdal:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[str, ...]]] = []

    def OpenEx(self, uri: str, open_options: Tuple[str, ...] = ()) -> object:
        self.calls.append((uri, open_options))
        return object()


def test_direct_config_reaches_user_runtime_through_the_complete_pipeline() -> None:
    """Specの全アクセス順序とruntime callbackの遅延評価を垂直スライスで保証するために必要である。"""
    runtime = FakeGdal()
    dependency_calls: List[str] = []
    dependencies = DependencyRegistry(
        {"gdal": lambda: dependency_calls.append("gdal") or runtime}
    )
    pipeline = AccessPipeline(
        source_adapters=(DirectAdapter(),),
        resolver=Resolver(),
        execution_selector=ExecutionAdapterSelector((PyogrioAdapter(), GdalAdapter())),
        dependencies=dependencies,
    )
    config = Config(
        source_type="direct",
        settings={
            "uri": "https://files.example/rivers.zip",
            "format": "shapefile",
            "archive": "zip",
            "encoding": "cp932",
        },
    )

    assert dependency_calls == []
    data = pipeline.open(config)

    assert data is not None
    assert dependency_calls == ["gdal"]
    assert runtime.calls[0][0].startswith("/vsizip//vsicurl/")


def test_complete_pipeline_honours_explicit_execution_adapter() -> None:
    """自動選択を迂回せず、利用者の明示Adapter指定をSelector経由で尊重するために必要である。"""

    class FakePyogrio:
        def read_dataframe(self, uri: str, **options: object) -> str:
            return "pyogrio-data"

    pipeline = AccessPipeline(
        source_adapters=(DirectAdapter(),),
        resolver=Resolver(),
        execution_selector=ExecutionAdapterSelector((GdalAdapter(), PyogrioAdapter())),
        dependencies=DependencyRegistry({"pyogrio": lambda: FakePyogrio()}),
    )
    config = Config(
        source_type="direct",
        settings={"uri": "/data/rivers.shp", "format": "shapefile"},
    )

    assert pipeline.open(config, adapter="pyogrio") == "pyogrio-data"
