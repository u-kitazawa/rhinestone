"""Open an explicit resource with user-owned GDAL."""

import os

from osgeo import gdal

from rhinestone import Config, configure

data_uri = os.environ["RHINESTONE_GDAL_URI"]
data_format = os.environ.get("RHINESTONE_GDAL_FORMAT", "geotiff")
app = configure(
    dependencies={"gdal": gdal},
)
resource = app.resolve(
    Config(
        source_id="direct",
        settings={"uri": data_uri, "format": data_format},
    )
)

dataset = resource.open("gdal")
print("resource:", resource.uri)
print("GDAL dataset:", dataset)
