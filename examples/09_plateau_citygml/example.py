"""Open one explicitly selected CityGML member from a PLATEAU ZIP resource."""

import os

from osgeo import gdal

from rhinestone import Reference, configure
from rhinestone.catalogs import BUILTIN, Catalog

app = configure(
    catalog=Catalog(provider for provider in BUILTIN if provider.id == "plateau"),
)
resource = app.load(
    Reference(
        "plateau",
        parameters={
            "resource_id": os.environ["RHINESTONE_PLATEAU_RESOURCE_ID"],
            "archive": "zip",
            "entry_point": os.environ["RHINESTONE_PLATEAU_CITYGML_MEMBER"],
        },
    )
)
dataset = resource.open("gdal", runtime=gdal)
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("layer count:", dataset.GetLayerCount())
