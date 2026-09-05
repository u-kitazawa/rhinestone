# 07 — Search and fetch

This live demo performs federated CKAN/e-Stat search, keeps results grouped by
provider, converts one SearchResult to Config, and sends it through the normal
resolution pipeline.

## Setup

Register for an e-Stat application ID and choose a CKAN site with an enabled
Action API, then run:

```console
cd rhinestone
uv sync --dev
export RHINESTONE_CKAN_ENDPOINT="https://www.geospatial.jp/ckan"
export RHINESTONE_ESTAT_APP_ID="your-application-id"
# Optional for protected CKAN (choose one if needed).
# export RHINESTONE_CKAN_API_TOKEN="your-token"
# export RHINESTONE_CKAN_API_KEY="your-api-key"
export RHINESTONE_QUERY="人口"
export RHINESTONE_RESULT_PROVIDER="estat"
uv run python docs/examples/07_search_and_fetch/example.py
```

`RHINESTONE_RESULT_PROVIDER` must be `ckan` or `estat` and that provider must
return at least one result. Results vary with live provider state; this is a demo
rather than a deterministic CI check. Selecting a result never bypasses Config
validation or Source resolution.

For G空間情報センター, the CKAN endpoint is `https://www.geospatial.jp/ckan`,
not the `front.geospatial.jp` website host.
