"""Open an explicit resource with user-owned GDAL."""

import os

from osgeo import gdal

from rhinestone import Config, configure
from rhinestone.adapters import DirectAdapter
from rhinestone.adapters.execution import GdalAdapter

data_uri = os.environ["RHINESTONE_GDAL_URI"]
data_format = os.environ.get("RHINESTONE_GDAL_FORMAT", "geotiff")
app = configure(
    dependencies={"gdal": lambda: gdal},
    source_adapters=(DirectAdapter(),),
    execution_adapters=(GdalAdapter(),),
)
resource = app.resolve(
    Config(
        source_type="direct",
        settings={"uri": data_uri, "format": data_format},
    )
)

dataset = resource.open(adapter="gdal")
print("resource:", resource.uri)
print("GDAL dataset:", dataset)
