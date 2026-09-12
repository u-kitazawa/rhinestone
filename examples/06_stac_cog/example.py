"""Resolve a STAC asset and open its COG with user-owned Rasterio."""

import os

import rasterio

from rhinestone import Config, Provider, configure

endpoint = os.environ["RHINESTONE_STAC_ENDPOINT"]
collection_id = os.environ["RHINESTONE_STAC_COLLECTION_ID"]
item_id = os.environ["RHINESTONE_STAC_ITEM_ID"]
asset_key = os.environ["RHINESTONE_STAC_ASSET_KEY"]
app = configure(
    sources=(Provider("earth-search", "stac", {"endpoint": endpoint}),),
    dependencies={"rasterio": rasterio},
)
resource = app.resolve(
    Config(
        source_id="earth-search",
        settings={
            "collection_id": collection_id,
            "item_id": item_id,
            "asset_key": asset_key,
        },
    )
)

with resource.open("rasterio") as dataset:
    print("resource:", resource.uri)
    print("metadata:", resource.metadata)
    print("raster size:", dataset.width, dataset.height)
