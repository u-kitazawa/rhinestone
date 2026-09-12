"""Open one explicitly selected CityGML member from a PLATEAU ZIP resource."""

import os

from osgeo import gdal

from rhinestone import Config, configure, sources
from rhinestone.models import RuntimeFactory

app = configure(
    sources=(sources.PLATEAU,),
    dependencies={"gdal": RuntimeFactory(lambda: gdal)},
)
resource = app.resolve(
    Config(
        "plateau",
        {
            "resource_id": os.environ["RHINESTONE_PLATEAU_RESOURCE_ID"],
            "archive": "zip",
            "entry_point": os.environ["RHINESTONE_PLATEAU_CITYGML_MEMBER"],
        },
    )
)
dataset = resource.open("gdal")
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("layer count:", dataset.GetLayerCount())
