"""Built-in execution adapters."""

from .base import ExecutionAdapter
from .gdal import GdalAdapter
from .json_service import JsonServiceAdapter
from .pyogrio import PyogrioAdapter
from .rasterio import RasterioAdapter

__all__ = [
    "ExecutionAdapter",
    "GdalAdapter",
    "JsonServiceAdapter",
    "PyogrioAdapter",
    "RasterioAdapter",
]
