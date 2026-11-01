"""Open an explicit resource with user-owned GDAL."""

import os

from osgeo import gdal

from rhinestone import Reference, configure

data_uri = os.environ["RHINESTONE_GDAL_URI"]
data_format = os.environ.get("RHINESTONE_GDAL_FORMAT", "geotiff")
app = configure()
resource = app.load(
    Reference(
        provider_id="direct",
        parameters={"uri": data_uri, "format": data_format},
    )
)

dataset = resource.open("gdal", runtime=gdal)
print("resource:", resource.uri)
print("GDAL dataset:", dataset)
