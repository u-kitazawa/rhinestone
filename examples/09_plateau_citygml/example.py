"""Open one explicitly selected CityGML member from a PLATEAU ZIP resource."""

import os

from osgeo import gdal

from rhinestone import Config, ProviderConfig, configure


def get_json(url, params):
    import requests

    return requests.get(url, params=params, timeout=30).json()


app = configure(
    providers={"plateau": ProviderConfig("plateau")},
    dependencies={"http-json": lambda: get_json, "gdal": lambda: gdal},
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
