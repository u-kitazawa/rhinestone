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
# Optional for protected APIs (choose one).
export RHINESTONE_STAC_API_TOKEN="your-bearer-token"
# export RHINESTONE_STAC_API_KEY="your-api-key"
uv run python docs/examples/06_stac_cog/example.py
```

The selected asset must advertise a COG media type containing
`profile=cloud-optimized`; Rhinestone intentionally does not infer COG from a
`.tif` suffix. The STAC server and asset must be publicly reachable unless your
injected transport/runtime handles authentication. Tokens use `Authorization:
Bearer ...`; API keys use `X-API-Key`.
