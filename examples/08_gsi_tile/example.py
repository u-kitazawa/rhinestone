"""Open GSI Standard Map tiles through user-owned GDAL."""

from osgeo import gdal

from rhinestone import Reference, configure
from rhinestone.catalogs import BUILTIN, Catalog

app = configure(
    catalog=Catalog(provider for provider in BUILTIN if provider.id == "gsi"),
)

resource = app.load(Reference("gsi", parameters={"id": "std"}))
dataset = resource.open("gdal", runtime=gdal)
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("raster size:", dataset.RasterXSize, dataset.RasterYSize)
