"""Resolve a STAC asset and open its COG with user-owned Rasterio."""

import os
import sys
from pathlib import Path

import rasterio

from rhinestone import Config, configure
from rhinestone.adapters import StacAdapter
from rhinestone.execution_adapters import RasterioAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _support.http_json import get_json  # noqa: E402

endpoint = os.environ["RHINESTONE_STAC_ENDPOINT"]
collection_id = os.environ["RHINESTONE_STAC_COLLECTION_ID"]
item_id = os.environ["RHINESTONE_STAC_ITEM_ID"]
asset_key = os.environ["RHINESTONE_STAC_ASSET_KEY"]
adapter_kwargs = {"get_json": get_json}
if os.environ.get("RHINESTONE_STAC_API_TOKEN"):
    adapter_kwargs["api_token"] = os.environ["RHINESTONE_STAC_API_TOKEN"]
elif os.environ.get("RHINESTONE_STAC_API_KEY"):
    adapter_kwargs["api_key"] = os.environ["RHINESTONE_STAC_API_KEY"]
app = configure(
    dependencies={"rasterio": lambda: rasterio},
    source_adapters=(StacAdapter(endpoint=endpoint, **adapter_kwargs),),
    execution_adapters=(RasterioAdapter(),),
)
resource = app.resolve(
    Config(
        source_type="stac",
        settings={
            "endpoint": endpoint,
            "collection_id": collection_id,
            "item_id": item_id,
            "asset_key": asset_key,
        },
    )
)

with resource.open(adapter="rasterio") as dataset:
    print("resource:", resource.uri)
    print("metadata:", resource.metadata)
    print("raster size:", dataset.width, dataset.height)
