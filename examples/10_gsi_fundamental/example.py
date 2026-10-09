"""Open an already-downloaded GSI Fundamental Data basic-item file."""

import os

from osgeo import gdal

from rhinestone import Provider, Reference, configure
from rhinestone.catalogs import Catalog

app = configure(
    catalog=Catalog((Provider("gsi-fundamental", "gsi-fundamental"),)),
)
resource = app.load(
    Reference(
        "gsi-fundamental",
        parameters={
            "dataset": "basic",
            "path": os.environ["RHINESTONE_GSI_FUNDAMENTAL_PATH"],
            "metadata": {
                "mesh": os.environ["RHINESTONE_GSI_MESH"],
                "feature_type": "BldA",
                "schema_version": os.environ["RHINESTONE_GSI_SCHEMA_VERSION"],
                "download_spec_version": os.environ["RHINESTONE_GSI_DOWNLOAD_SPEC"],
                "crs": os.environ["RHINESTONE_GSI_CRS"],
                "source_url": "https://service.gsi.go.jp/kiban/",
            },
        },
    )
)
dataset = resource.open("gdal", runtime=gdal)
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("layer count:", dataset.GetLayerCount())
