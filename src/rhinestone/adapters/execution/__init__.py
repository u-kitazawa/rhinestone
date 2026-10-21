"""Public Adapter exports loaded only when explicitly imported."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import ExecutionAdapter
    from .gdal import GdalAdapter
    from .json_service import JsonServiceAdapter
    from .pyogrio import PyogrioAdapter
    from .rasterio import RasterioAdapter

_EXPORTS = {
    "ExecutionAdapter": ".base",
    "GdalAdapter": ".gdal",
    "JsonServiceAdapter": ".json_service",
    "PyogrioAdapter": ".pyogrio",
    "RasterioAdapter": ".rasterio",
}


def __getattr__(name: str) -> Any:
    try:
        module = _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


__all__ = [
    "ExecutionAdapter",
    "GdalAdapter",
    "JsonServiceAdapter",
    "PyogrioAdapter",
    "RasterioAdapter",
]
