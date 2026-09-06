# 07 — Search and fetch

This live demo performs federated G Spatial Information Center CKAN/e-Stat search, keeps results grouped by source, converts one SearchResult to Config, and sends it through the normal resolution pipeline.

## Setup

Register for an e-Stat application ID, then run:

```console
cd rhinestone
uv sync --dev
export RHINESTONE_ESTAT_APP_ID="your-application-id"
export RHINESTONE_QUERY="人口"
export RHINESTONE_RESULT_SOURCE="estat"
uv run python examples/07_search_and_fetch/example.py
```

`RHINESTONE_RESULT_SOURCE` must be `geospatial-jp` or `estat`, and that source must return at least one result. The G Spatial Information Center endpoint comes from `sources.GEOSPATIAL_JP`; HTTP communication for both sources uses Rhinestone's built-in transport.

Results vary with live provider state; this is a demo rather than a deterministic CI check. Selecting a result never bypasses Config validation or Source resolution.
