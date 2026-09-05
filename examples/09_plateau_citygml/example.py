"""Open one explicitly selected CityGML member from a PLATEAU ZIP resource."""

import os

from osgeo import gdal

from rhinestone import Config, configure
from rhinestone.adapters import PlateauAdapter
from rhinestone.adapters.execution import GdalAdapter


def get_json(url, params):
    import requests

    return requests.get(url, params=params, timeout=30).json()


app = configure(
    dependencies={"gdal": lambda: gdal},
    source_adapters=(PlateauAdapter(get_json),),
    execution_adapters=(GdalAdapter(),),
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
