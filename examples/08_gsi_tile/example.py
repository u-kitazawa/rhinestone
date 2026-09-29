"""Open GSI Standard Map tiles through user-owned GDAL."""

from osgeo import gdal

from rhinestone import Config, configure, sources

app = configure(
    sources=(sources.GSI,),
)

resource = app.resolve(Config("gsi", {"id": "std"}))
dataset = resource.open("gdal", runtime=gdal)
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
