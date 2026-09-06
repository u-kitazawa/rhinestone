"""Open an already-downloaded GSI Fundamental Data basic-item file."""

import os

from osgeo import gdal

from rhinestone import Config, ProviderConfig, configure

app = configure(
    providers={"gsi-fundamental": ProviderConfig("gsi-fundamental")},
    dependencies={"gdal": lambda: gdal},
)
resource = app.resolve(
    Config(
        "gsi-fundamental",
        {
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
dataset = resource.open("gdal")
print("URI:", resource.uri)
print("provenance:", resource.provenance)
print("layer count:", dataset.GetLayerCount())
