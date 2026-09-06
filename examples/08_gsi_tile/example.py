"""Open GSI Standard Map tiles through user-owned GDAL."""

from osgeo import gdal

from rhinestone import Config, ProviderConfig, configure

app = configure(
    providers={"gsi": ProviderConfig("gsi-tile")},
    dependencies={"gdal": lambda: gdal},
)

resource = app.resolve(Config("gsi", {"id": "std"}))
dataset = resource.open("gdal")
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
