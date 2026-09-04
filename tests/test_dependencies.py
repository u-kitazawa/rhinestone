import pytest

from rhinestone.errors import DependencyUnavailableError
from rhinestone.registry import DependencyRegistry


def test_dependency_callback_is_lazy_and_cached_per_registry() -> None:
    """Optional runtime を import 時に要求せず、利用者所有の実体を遅延取得するために必要である。"""
    calls = []
    runtime = object()
    registry = DependencyRegistry({"gdal": lambda: calls.append("gdal") or runtime})

    assert calls == []
    assert registry.get("gdal") is runtime
    assert registry.get("gdal") is runtime
    assert calls == ["gdal"]


def test_missing_dependency_has_a_specific_failure() -> None:
    """依存不足を一般的な RuntimeError と区別して呼び出し側が対処するために必要である。"""
    registry = DependencyRegistry({})

    with pytest.raises(DependencyUnavailableError, match="rasterio"):
        registry.get("rasterio")


def test_dependency_factory_failure_preserves_the_cause() -> None:
    """利用者 callback の失敗原因を失わず境界エラーとして報告するために必要である。"""
    import_error = ImportError("GDAL is not installed")

    def unavailable_gdal() -> object:
        raise import_error

    registry = DependencyRegistry({"gdal": unavailable_gdal})

    with pytest.raises(DependencyUnavailableError) as captured:
        registry.get("gdal")

    assert captured.value.__cause__ is import_error
