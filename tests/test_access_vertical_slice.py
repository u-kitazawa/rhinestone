from typing import List, Tuple

from rhinestone import Config, RuntimeFactory, configure


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
    app = configure(
        dependencies={
            "gdal": RuntimeFactory(lambda: dependency_calls.append("gdal") or runtime)
        }
    )
    config = Config(
        source_id="direct",
        settings={
            "uri": "https://files.example/rivers.zip",
            "format": "shapefile",
            "archive": "zip",
            "encoding": "cp932",
        },
    )

    assert dependency_calls == []
    data = app.open(config, library="gdal")

    assert data is not None
    assert dependency_calls == ["gdal"]
    assert runtime.calls[0][0].startswith("/vsizip//vsicurl/")


def test_complete_pipeline_honours_explicit_execution_adapter() -> None:
    """自動選択を迂回せず、利用者の明示Adapter指定をSelector経由で尊重するために必要である。"""

    class FakePyogrio:
        def read_dataframe(self, uri: str, **options: object) -> str:
            return "pyogrio-data"

    app = configure(dependencies={"pyogrio": RuntimeFactory(FakePyogrio)})
    config = Config(
        source_id="direct",
        settings={"uri": "/data/rivers.shp", "format": "shapefile"},
    )

    assert app.open(config, library="pyogrio") == "pyogrio-data"
