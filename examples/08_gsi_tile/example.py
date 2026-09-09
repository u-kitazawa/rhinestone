"""Open GSI Standard Map tiles through user-owned GDAL."""

from osgeo import gdal

from rhinestone import Config, RuntimeFactory, configure, sources

app = configure(
    sources=(sources.GSI,),
    dependencies={"gdal": RuntimeFactory(lambda: gdal)},
)

resource = app.resolve(Config("gsi", {"id": "std"}))
dataset = resource.open("gdal")
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
