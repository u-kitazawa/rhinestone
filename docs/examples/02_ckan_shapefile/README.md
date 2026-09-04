# 02 — CKAN Shapefile

This live example resolves a known CKAN resource using `resource_show` and
`package_show`. Choose a CKAN resource explicitly; the example does not guess a
resource from a dataset page.

## Setup

```console
cd rhinestone
uv sync --dev
export RHINESTONE_CKAN_ENDPOINT="https://www.geospatial.jp/ckan"
export RHINESTONE_CKAN_RESOURCE_ID="the-resource-uuid"
# Optional for protected CKAN (choose one; never commit the value).
export RHINESTONE_CKAN_API_TOKEN="your-token"
# export RHINESTONE_CKAN_API_KEY="your-api-key"
uv run python docs/examples/02_ckan_shapefile/example.py
```

`RHINESTONE_CKAN_ENDPOINT` is the site root without `/api/3/action`. Select a
ZIP Shapefile resource to see archive-related access knowledge. No GDAL is
needed because this example resolves metadata without opening the data.
For G空間情報センター, use `https://www.geospatial.jp/ckan`; the
`front.geospatial.jp` website host does not expose the CKAN Action API path.

The command performs live network requests and can fail if the provider changes
or removes the resource.

The token uses CKAN's `Authorization` header; the API key uses `X-CKAN-API-Key`.
