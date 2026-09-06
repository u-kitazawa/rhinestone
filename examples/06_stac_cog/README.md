# 06 — STAC COG with Rasterio

This live example resolves one explicitly selected STAC asset and delegates the
COG URI to a user-owned Rasterio installation.

## Setup

```console
cd rhinestone
uv sync --dev
UV_CACHE_DIR=/tmp/rhinestone-uv-cache uv pip install rasterio
export RHINESTONE_STAC_ENDPOINT="https://your-stac.example"
export RHINESTONE_STAC_COLLECTION_ID="collection-id"
export RHINESTONE_STAC_ITEM_ID="item-id"
export RHINESTONE_STAC_ASSET_KEY="data-asset-key"
uv run python examples/06_stac_cog/example.py
```

The selected asset must advertise a COG media type containing
`profile=cloud-optimized`; Rhinestone intentionally does not infer COG from a
`.tif` suffix. HTTP metadata retrieval uses Rhinestone's built-in transport, so
the STAC endpoint used by this public example must be reachable without custom
transport injection.
