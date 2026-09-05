"""Open GSI Standard Map tiles through user-owned GDAL."""

from osgeo import gdal

from rhinestone import Config, configure
from rhinestone.adapters import GsiTileAdapter
from rhinestone.adapters.execution import GdalAdapter

app = configure(
    dependencies={"gdal": lambda: gdal},
    source_adapters=(GsiTileAdapter(),),
    execution_adapters=(GdalAdapter(),),
)

resource = app.resolve(Config("gsi-tile", {"id": "std"}))
dataset = resource.open("gdal")
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
