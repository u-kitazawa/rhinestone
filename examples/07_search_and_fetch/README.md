# 07 — Search and fetch

This live demo performs a G Spatial Information Center CKAN search, keeps results grouped by source, converts one SearchResult to Config, and sends it through the normal resolution pipeline.

## Setup

```console
cd rhinestone
uv sync --dev
export RHINESTONE_QUERY="人口"
uv run python examples/07_search_and_fetch/example.py
```

The G Spatial Information Center endpoint comes from `sources.GEOSPATIAL_JP`; HTTP communication uses Rhinestone's built-in transport.

Results vary with live provider state; this is a demo rather than a deterministic CI check. Selecting a result never bypasses Config validation or Source resolution.
